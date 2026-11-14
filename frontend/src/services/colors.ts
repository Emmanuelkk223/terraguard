// Inferno colour stops: perceptually uniform, monotonic in luminance, colour-blind safe.
const INFERNO: [number, number, number][] = [
  [0, 0, 4], [31, 12, 72], [85, 15, 109], [136, 34, 106],
  [186, 54, 85], [227, 89, 51], [249, 140, 10], [249, 201, 50], [252, 255, 164],
];

export function infernoColor(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (INFERNO.length - 1);
  const i = Math.min(INFERNO.length - 2, Math.floor(x));
  const f = x - i;
  const c = INFERNO[i].map((v, k) => Math.round(v + (INFERNO[i + 1][k] - v) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

/** Readable label colour on an inferno cell. */
export function textOn(t: number): string {
  return t > 0.62 ? "#10151c" : "#f3efe8";
}
