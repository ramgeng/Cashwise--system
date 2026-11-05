// Indian-style money: "₹1.94 L" for lakhs, "₹45,000" below a lakh.
export function inr(n, { signed = false } = {}) {
  if (n === null || n === undefined) return "–";
  const neg = n < 0;
  const a = Math.abs(n);
  const body = a >= 100000 ? `₹${(a / 100000).toFixed(2)} L` : `₹${a.toLocaleString("en-IN")}`;
  if (neg) return `−${body}`;
  return signed ? `+${body}` : body;
}

export function shortInr(n) {
  const a = Math.abs(n);
  const s = a >= 100000 ? `${(a / 100000).toFixed(a >= 1000000 ? 0 : 1)}L` : `${Math.round(a / 1000)}k`;
  return n < 0 ? `−${s}` : s;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function day(iso) {
  const d = new Date(iso + "T00:00:00");
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function longDay(iso) {
  const d = new Date(iso + "T00:00:00");
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}
