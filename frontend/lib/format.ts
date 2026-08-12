/** Currency and number formatting.
 *
 * Three-tier Indian numbering, ported from the prototype: crore at >= 1,00,00,000,
 * lakh at >= 1,00,000, plain rupees below. Not a flat symbol swap.
 *
 * The rate is supplied by the API rather than hardcoded here -- in the
 * prototype `INR_RATE = 83` was a magic number buried in profile.js, which
 * meant changing it required a code change and a rebuild.
 */

let rate = 83;

export function setInrRate(r: number) {
  rate = r;
}

export function money(usd: number): string {
  const r = usd * rate;
  if (!isFinite(r)) return "—";
  const abs = Math.abs(r);
  const sign = r < 0 ? "-" : "";
  if (abs >= 1e7) {
    const cr = abs / 1e7;
    // A whole number of crore prints without a decimal: "Rs 8 Cr", not
    // "Rs 8.0 Cr". Every cheque a student can select is a whole number at the
    // configured rate, and a trailing .0 on all of them made round figures look
    // like measurements.
    const shown = cr >= 100 ? Math.round(cr) : Math.round(cr * 10) / 10;
    return `${sign}₹${Number.isInteger(shown) ? shown : shown.toFixed(1)} Cr`;
  }
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)} L`;
  return `${sign}₹${Math.round(abs).toLocaleString("en-IN")}`;
}

/** For values already expressed in millions of USD. */
export const moneyM = (m: number) => money(m * 1e6);

export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;
export const num = (x: number, digits = 1) => x.toFixed(digits);
export const mult = (x: number, digits = 1) =>
  isFinite(x) ? `${x.toFixed(digits)}x` : "—";

export function months(x: number): string {
  if (!isFinite(x)) return "—";
  return `${x.toFixed(1)} mo`;
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}
