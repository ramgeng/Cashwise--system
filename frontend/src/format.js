// Indian-style money: "₹1.94 L" for lakhs, "₹45,000" below a lakh.
export function inr(n, { signed = false } = {}) {
  if (n === null || n === undefined) return "–";
  const a = Math.abs(n);
  const body = a >= 100000 ? `₹${(a / 100000).toFixed(2)} L` : `₹${Math.round(a).toLocaleString("en-IN")}`;
  if (n < 0) return `−${body}`;
  return signed ? `+${body}` : body;
}

// "left" or "short" phrasing for a balance.
export function leftOrShort(n) {
  return n < 0 ? `${inr(-n)} short` : `${inr(n)} left`;
}

export function shortInr(n) {
  const a = Math.abs(n);
  const s = a >= 100000 ? `${(a / 100000).toFixed(a >= 1000000 ? 0 : 1)}L` : `${Math.round(a / 1000)}k`;
  return n < 0 ? `−${s}` : s;
}

// Backend text uses "Rs 1.94 L"; show it the same way as the rest of the UI.
export function money(text) {
  return (text || "").replace(/-\s?Rs\.?\s?/g, "−₹").replace(/Rs\.?\s?/g, "₹");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const LONG_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const parse = (iso) => new Date(iso.slice(0, 10) + "T00:00:00");

export const day = (iso) => { const d = parse(iso); return `${d.getDate()} ${MONTHS[d.getMonth()]}`; };
export const longDay = (iso) => { const d = parse(iso); return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`; };
export const monthYear = (iso) => { const d = parse(iso); return `${LONG_MONTHS[d.getMonth()]} ${d.getFullYear()}`; };
export const addDays = (iso, n) => {
  const d = parse(iso);
  d.setDate(d.getDate() + n);
  const pad = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

// "5 Nov 2026, 6:46 pm" in the viewer's own time, from an ISO timestamp.
export function when(iso) {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}
