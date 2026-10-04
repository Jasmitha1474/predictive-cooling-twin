export function temperatureToColor(temp: number): [number, number, number] {
  if (temp < 65) return [0, 0, 1];
  if (temp < 75) return [0, 1, 0];
  if (temp < 80) return [1, 1, 0];
  if (temp < 85) return [1, 0.5, 0];
  return [1, 0, 0];
}

export function temperatureToHex(temp: number): string {
  const [r, g, b] = temperatureToColor(temp);
  return `#${Math.round(r * 255).toString(16).padStart(2, '0')}${Math.round(g * 255).toString(16).padStart(2, '0')}${Math.round(b * 255).toString(16).padStart(2, '0')}`;
}

export function flowRateToSpeed(flowRate: number, maxFlow: number): number {
  return (flowRate / maxFlow) * 2;
}
