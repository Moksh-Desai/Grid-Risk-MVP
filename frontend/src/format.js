export const pct = (p, digits = 0) => (p == null ? "–" : `${(p * 100).toFixed(digits)}%`);
export const num = (v, digits = 0) =>
  v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
export const money = (musd) => {
  if (musd == null) return "–";
  if (Math.abs(musd) >= 1000) return `$${(musd / 1000).toFixed(1)}B`;
  if (Math.abs(musd) >= 1) return `$${musd.toFixed(1)}M`;
  return `$${(musd * 1000).toFixed(0)}k`;
};
export const months = (m) => {
  if (m == null) return "–";
  const y = m / 12;
  return y >= 2 ? `${y.toFixed(1)} yr` : `${Math.round(m)} mo`;
};
export const monthYear = (iso) =>
  iso ? new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", year: "numeric" }) : "–";

export const TECH_LABEL = {
  solar: "Solar",
  wind: "Wind",
  storage: "Storage",
  hybrid: "Solar/wind + storage",
  gas: "Gas",
};

export const TECH_COLOR = {
  solar: "#d4a017",
  wind: "#3f7cac",
  storage: "#7a5195",
  hybrid: "#2f855a",
  gas: "#8a8a8a",
};

export const LEVEL_CLASS = { Low: "lvl-low", Moderate: "lvl-mid", High: "lvl-high" };
