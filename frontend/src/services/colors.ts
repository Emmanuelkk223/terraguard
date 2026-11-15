// Colour ramps for the calendar and the map. All three are perceptually uniform (equal steps look equal) and
// increase steadily in lightness, so the order dark -> light is readable in greyscale as well as in colour.
// Inferno is the default; Viridis and Cividis are offered because Cividis is designed to look the same to people
// with red-green colour-vision deficiency. Meaning never rests on colour alone: every cell also shows its number,
// and unusual months carry a symbol.

export type RampName = "inferno" | "viridis" | "cividis";

const hex = (list: string[]): [number, number, number][] =>
  list.map((h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]);

const STOPS: Record<RampName, [number, number, number][]> = {
  inferno: [[0, 0, 4], [31, 12, 72], [85, 15, 109], [136, 34, 106], [186, 54, 85], [227, 89, 51], [249, 140, 10], [249, 201, 50], [252, 255, 164]],
  viridis: hex(["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"]),
  cividis: hex(["#00224e", "#123570", "#3b496c", "#575d6d", "#707173", "#8a8678", "#a59c74", "#c3b369", "#e1cc55", "#fee838"]),
};

export const RAMP_LABEL: Record<RampName, string> = {
  inferno: "Inferno (default)",
  viridis: "Viridis",
  cividis: "Cividis (colour-blind optimised)",
};
export const RAMP_NAMES = Object.keys(STOPS) as RampName[];
export const DEFAULT_RAMP: RampName = "inferno";

function channels(ramp: RampName, t: number): [number, number, number] {
  const stops = STOPS[ramp];
  const x = Math.min(1, Math.max(0, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  return stops[i].map((v, k) => Math.round(v + (stops[i + 1][k] - v) * f)) as [number, number, number];
}

export function rampColor(ramp: RampName, t: number): string {
  const c = channels(ramp, t);
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

const linear = (v: number) => {
  const s = v / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const luminance = ([r, g, b]: [number, number, number]) => 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);

/** Whichever of near-black or near-white text has the higher WCAG contrast on this cell. */
export function textOn(ramp: RampName, t: number): string {
  const l = luminance(channels(ramp, t));
  const lightText = (1.05) / (l + 0.05);
  const darkText = (l + 0.05) / (0.008 + 0.05);
  return lightText >= darkText ? "#f7f4ee" : "#10151c";
}

export function loadRamp(): RampName {
  try {
    const saved = window.localStorage.getItem("terraguard.ramp");
    if (saved && saved in STOPS) return saved as RampName;
  } catch {
    /* storage unavailable: use the default */
  }
  return DEFAULT_RAMP;
}

export function saveRamp(ramp: RampName): void {
  try {
    window.localStorage.setItem("terraguard.ramp", ramp);
  } catch {
    /* storage unavailable: the choice just will not persist */
  }
}
