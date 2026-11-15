import { useEffect, useMemo, useRef, useState } from "react";

/**
 * The landing page's animated map: one burning season over West Africa, month by month, from real data (public/landing-map.json, built by
 * data_pipeline/landing_map.py). A satellite sweeps across each month and the month's active squares light up behind it.
 * Countries can be hovered and clicked to open them in the calendar.
 */

interface Frame { label: string; month: number; cell_days: number; points: [number, number, number][] }
interface MapData {
  width: number;
  height: number;
  season: string;
  source: string;
  countries: { iso2: string; name: string; d: string; cx: number; cy: number }[];
  frames: Frame[];
}

interface Props {
  onPick?: (iso2: string, name: string) => void;
}

const SWEEP_S = 2.6; // seconds for the satellite to cross the map
const HOLD_S = 2.4; // seconds the finished month stays before the next
const fmt = (n: number) => n.toLocaleString("en-GB");

// Fire colours: dim red for a few days, bright yellow-white for the busiest squares.
function fireColour(w: number): string {
  const stops: [number, [number, number, number]][] = [[0, [160, 40, 60]], [0.45, [234, 90, 43]], [0.75, [242, 184, 75]], [1, [255, 244, 200]]];
  for (let i = 1; i < stops.length; i += 1) {
    if (w <= stops[i][0]) {
      const [a, ca] = stops[i - 1], [b, cb] = stops[i];
      const t = (w - a) / (b - a);
      return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * t)).join(",")})`;
    }
  }
  return "rgb(255,244,200)";
}

function useCountUp(target: number, ms = 900): number {
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = performance.now(), a = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - (1 - t) ** 3;
      setValue(Math.round(a + (target - a) * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
      else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);
  return value;
}

export default function FireMap({ onPick }: Props) {
  const [data, setData] = useState<MapData | null>(null);
  const [index, setIndex] = useState(3); // January: the peak, shown first
  const [playing, setPlaying] = useState(true);
  const [hovered, setHovered] = useState<string | null>(null);
  const [sweep, setSweep] = useState(0); // bumps to restart the sweep animation
  const reduced = useMemo(() => Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches), []);

  useEffect(() => {
    fetch("/landing-map.json").then((r) => (r.ok ? r.json() : null)).then(setData).catch(() => setData(null));
  }, []);
  useEffect(() => {
    if (!data || !playing || reduced) return;
    const id = window.setTimeout(() => {
      setIndex((i) => (i + 1) % data.frames.length);
      setSweep((n) => n + 1);
    }, (SWEEP_S + HOLD_S) * 1000);
    return () => window.clearTimeout(id);
  }, [data, playing, index, reduced]);

  const frame = data?.frames[index];
  const count = useCountUp(frame?.cell_days ?? 0);
  const peak = data ? Math.max(...data.frames.map((f) => f.cell_days)) : 1;

  if (!data || !frame) {
    return <div className="firemap firemap-loading" aria-hidden="true"><div className="firemap-scan" /></div>;
  }
  const { width: W, height: H } = data;
  const choose = (i: number) => { setIndex(i); setSweep((n) => n + 1); setPlaying(false); };

  return (
    <figure className="firemap" aria-label={`Map of West Africa: where it burned in ${frame.label}, from NASA satellite data`}>
      <div className="firemap-top">
        <span className="live-dot" aria-hidden="true" />
        <span><b>{frame.label}</b> · {fmt(count)} active cell-days across West Africa</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="firemap-svg" role="img" aria-hidden="true">
        <defs>
          <filter id="fm-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3.2" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id="fm-swath" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#4cc0b3" stopOpacity="0" />
            <stop offset=".75" stopColor="#4cc0b3" stopOpacity=".16" />
            <stop offset="1" stopColor="#bff7ef" stopOpacity=".55" />
          </linearGradient>
          <radialGradient id="fm-ghana" cx="50%" cy="50%" r="60%">
            <stop offset="0" stopColor="#f2b84b" stopOpacity=".22" />
            <stop offset="1" stopColor="#f2b84b" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* graticule */}
        <g className="fm-grid">
          {Array.from({ length: 9 }, (_, i) => <line key={`v${i}`} x1={(i + 1) * W / 10} y1="0" x2={(i + 1) * W / 10} y2={H} />)}
          {Array.from({ length: 4 }, (_, i) => <line key={`h${i}`} x1="0" y1={(i + 1) * H / 5} x2={W} y2={(i + 1) * H / 5} />)}
        </g>

        {/* countries */}
        <g className="fm-countries">
          {data.countries.map((c) => (
            <path
              key={c.iso2}
              d={c.d}
              className={`fm-country${c.iso2 === "GH" ? " ghana" : ""}${hovered === c.iso2 ? " hover" : ""}`}
              onPointerEnter={() => setHovered(c.iso2)}
              onPointerLeave={() => setHovered((h) => (h === c.iso2 ? null : h))}
              onClick={() => onPick?.(c.iso2, c.name)}
            />
          ))}
        </g>

        {/* this month's burning, lit up as the satellite passes */}
        <g key={`${index}-${sweep}`} className="fm-fires" filter="url(#fm-glow)">
          {frame.points.map(([x, y, w], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={1.3 + w * 3.4}
              fill={fireColour(w)}
              style={{ animationDelay: reduced ? "0s" : `${(x / W) * SWEEP_S + (i % 7) * 0.02}s` }}
            />
          ))}
        </g>

        {/* the satellite and its scanning swath */}
        {!reduced && (
          <g key={`sat-${index}-${sweep}`} className="fm-sat" style={{ ["--sweep" as string]: `${SWEEP_S}s`, ["--w" as string]: `${W}px` }}>
            <rect x={-120} y={-20} width={120} height={H + 40} fill="url(#fm-swath)" transform="skewX(-8)" />
            <g transform="translate(-14 14)">
              <rect x="-5" y="-4" width="10" height="8" fill="#e8eef5" />
              <rect x="-19" y="-3" width="12" height="6" fill="#4cc0b3" />
              <rect x="7" y="-3" width="12" height="6" fill="#4cc0b3" />
              <circle r="2" fill="#ea7a2b" className="fm-sat-led" />
            </g>
          </g>
        )}

        {/* labels */}
        <g className="fm-labels">
          {data.countries.filter((c) => c.cx > 10 && c.cx < W - 10 && (c.iso2 === "GH" || hovered === c.iso2)).map((c) => (
            <g key={c.iso2} transform={`translate(${c.cx} ${c.cy})`} className={c.iso2 === "GH" ? "ghana" : ""}>
              {c.iso2 === "GH" && <circle r="46" fill="url(#fm-ghana)" className="fm-ghana-pulse" />}
              <text textAnchor="middle" dy="4">{c.name}</text>
            </g>
          ))}
        </g>
      </svg>

      <div className="firemap-timeline" role="group" aria-label="Month">
        <button type="button" className="fm-play" onClick={() => { setPlaying((p) => !p); if (!playing) setSweep((n) => n + 1); }}
          aria-label={playing ? "Pause the animation" : "Play the season"}>{playing ? "❚❚" : "▶"}</button>
        {data.frames.map((f, i) => (
          <button key={f.label} type="button" className={`fm-month${i === index ? " on" : ""}`} onClick={() => choose(i)} aria-pressed={i === index}
            title={`${f.label}: ${fmt(f.cell_days)} active cell-days`}>
            <span className="fm-bar" style={{ height: `${Math.max(8, (f.cell_days / peak) * 100)}%` }} />
            <span className="fm-name">{f.label.slice(0, 3)}</span>
          </button>
        ))}
      </div>
      <figcaption>
        Burning season {data.season}, real NASA FIRMS detections (MODIS and VIIRS). Watch the burning move south: its centre shifts from about 13°N in October to about 9°N by January.
        {onPick && " Click a country to open it."}
      </figcaption>
    </figure>
  );
}
