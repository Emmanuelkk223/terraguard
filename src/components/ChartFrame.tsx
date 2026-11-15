import { useRef, useState, type ReactNode } from "react";

const BG = "#0d1a28";
const SCALE = 2;
const HEADER = 46;
const FOOTER = 54;

/** Draws a Recharts chart (its SVG plus its HTML legend) onto a titled canvas and downloads it as a PNG. */
async function exportPng(container: HTMLElement, title: string, filename: string): Promise<void> {
  const svg = container.querySelector<SVGSVGElement>("svg.recharts-surface");
  if (!svg) throw new Error("No chart to export");
  const { width, height } = svg.getBoundingClientRect();
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  clone.setAttribute("viewBox", `0 0 ${width} ${height}`);
  clone.setAttribute("style", "font-family: 'Segoe UI', Arial, sans-serif");

  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Chart could not be rendered"));
      image.src = url;
    });

    const legend = [...container.querySelectorAll<HTMLElement>(".recharts-legend-item")].map((item) => {
      const icon = item.querySelector("svg path, svg line");
      return {
        text: item.textContent?.trim() ?? "",
        colour: icon?.getAttribute("stroke") && icon.getAttribute("stroke") !== "none" ? icon.getAttribute("stroke")! : icon?.getAttribute("fill") ?? "#8a9db2",
      };
    });

    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * SCALE);
    canvas.height = Math.round((height + HEADER + FOOTER) * SCALE);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas is not available");
    ctx.scale(SCALE, SCALE);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, width, height + HEADER + FOOTER);
    ctx.fillStyle = "#f2b84b";
    ctx.fillRect(0, 0, 4, HEADER - 10);
    ctx.fillStyle = "#e8eef5";
    ctx.font = "600 15px 'Segoe UI', Arial, sans-serif";
    ctx.fillText(title, 14, 24);
    ctx.drawImage(image, 0, HEADER, width, height);

    let x = 14;
    ctx.font = "12px 'Segoe UI', Arial, sans-serif";
    legend.forEach(({ text, colour }) => {
      ctx.fillStyle = colour;
      ctx.fillRect(x, HEADER + height + 8, 10, 10);
      ctx.fillStyle = "#c3cfdb";
      ctx.fillText(text, x + 15, HEADER + height + 17);
      x += 15 + ctx.measureText(text).width + 18;
    });
    ctx.fillStyle = "#8a9db2";
    ctx.font = "11px 'Segoe UI', Arial, sans-serif";
    ctx.fillText("TerraGuard · NASA FIRMS MODIS and VIIRS detections · detections are not unique fires", 14, HEADER + height + 42);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("Could not create the image");
    const link = document.createElement("a");
    const href = URL.createObjectURL(blob);
    link.href = href;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(href), 10_000);
  } finally {
    URL.revokeObjectURL(url);
  }
}

interface Props {
  title: string;
  filename: string;
  children: ReactNode;
}

export default function ChartFrame({ title, filename, children }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="chart-frame" ref={ref}>
      <button
        type="button" className="tool png"
        title="Download this chart as a PNG image"
        onClick={() => ref.current && exportPng(ref.current, title, filename).then(() => setError(null)).catch((e: Error) => setError(e.message))}
      >
        PNG
      </button>
      {children}
      {error && <span className="error inline">{error}</span>}
    </div>
  );
}
