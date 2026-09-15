// Display helpers. Exact raw values are always shown elsewhere; these only shorten or group for readability.

export function groupDigits(value: string | number): string {
  const s = String(value);
  const [int, frac] = s.split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return frac === undefined ? grouped : `${grouped}.${frac}`;
}

export function shortHex(hex: string, head = 6, tail = 4): string {
  return hex.length <= head + tail + 1 ? hex : `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

export function roundPercent(percent: string, digits = 4): string {
  const n = Number(percent);
  return Number.isFinite(n) ? n.toFixed(digits) : percent;
}

export function bytes(n: number): string {
  return `${groupDigits(n)} bytes`;
}
