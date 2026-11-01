export const DEFAULT_INPUT = {
  region: "PJM",
  technology: "solar",
  capacity_mw: 150,
  substation_id: "",
  phase: 0,
  upgrade_cost_per_kw: "",
  at_risk_per_kw: 25,
  reform_adjustment: false,
};

// Turn form state into the API payload (empty strings become nulls).
export function toPayload(input) {
  return {
    ...input,
    capacity_mw: Number(input.capacity_mw),
    phase: Number(input.phase),
    at_risk_per_kw: Number(input.at_risk_per_kw || 0),
    substation_id: input.substation_id || null,
    upgrade_cost_per_kw: input.upgrade_cost_per_kw === "" ? null : Number(input.upgrade_cost_per_kw),
  };
}
