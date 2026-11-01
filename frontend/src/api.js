import { API_BASE } from "./config";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail = body && body.detail ? body.detail : body;
    const msg = Array.isArray(detail)
      ? detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ")
      : typeof detail === "object"
        ? JSON.stringify(detail)
        : String(detail || res.statusText);
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return body;
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  meta: () => request("/api/meta"),
  substations: (region) => request(`/api/substations/${encodeURIComponent(region)}`),
  assess: (input) => request("/api/assess", json("POST", input)),
  alternatives: (input, limit = 25) => request(`/api/alternatives?limit=${limit}`, json("POST", input)),
  portfolio: (projects, reform) =>
    request("/api/portfolio", json("POST", { projects, reform_adjustment: reform })),
  portfolioCsv: (file, reform) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/portfolio/csv?reform_adjustment=${reform}`, { method: "POST", body: form });
  },
  market: () => request("/api/market"),
  model: () => request("/api/model"),
};

// Original MVP call, kept for anything still using it.
export const assessSite = (data) => request("/api/assess-site", json("POST", data));
