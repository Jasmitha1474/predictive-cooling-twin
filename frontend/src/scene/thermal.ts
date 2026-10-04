import * as THREE from 'three';

// Thermal colour scale. Bands are placed relative to the backend's threshold so that the
// colours mean the same thing whatever threshold the experiment uses:
//   normal < thr-15 <= elevated < thr-5 <= warning < thr <= critical (>= thr+5 strongest)
// This mirrors the brief's example (65/75/80/85 degC for an 80 degC threshold).
const STOPS: [number, string][] = [
  [-25, '#1b4dff'],
  [-15, '#17b8d6'],
  [-5, '#f2c94c'],
  [0, '#ff7a1a'],
  [5, '#ff2626'],
];
const COLS = STOPS.map(([o, c]) => [o, new THREE.Color(c)] as const);

export function thermalColor(tempC: number, thresholdC: number, out = new THREE.Color()): THREE.Color {
  const d = tempC - thresholdC;
  if (d <= COLS[0][0]) return out.copy(COLS[0][1]);
  for (let i = 1; i < COLS.length; i++) {
    if (d <= COLS[i][0]) {
      const [o0, c0] = COLS[i - 1];
      const [o1, c1] = COLS[i];
      return out.copy(c0).lerp(c1, (d - o0) / (o1 - o0));
    }
  }
  return out.copy(COLS[COLS.length - 1][1]);
}

export type Band = 'normal' | 'elevated' | 'warning' | 'critical';
export function thermalBand(tempC: number, thresholdC: number): Band {
  const d = tempC - thresholdC;
  if (d >= 0) return 'critical';
  if (d >= -5) return 'warning';
  if (d >= -15) return 'elevated';
  return 'normal';
}

/** Frame-rate independent exponential smoothing toward the latest backend value. */
export function damp(current: number, target: number, lambda: number, dt: number) {
  return THREE.MathUtils.damp(current, target, lambda, dt);
}
