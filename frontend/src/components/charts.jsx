// Small hand-rolled SVG charts. No chart library, so the bundle stays light.

const INK = "var(--ink)";
const MUTED = "var(--muted)";
const RULE = "var(--rule)";

// Horizontal P10-P50-P90 range on a shared axis.
export function RangeBar({ p10, p50, p90, max, format, marker, markerLabel }) {
  const W = 420;
  const H = 54;
  const pad = 8;
  const top = Math.max(max ?? p90 * 1.15, marker ?? 0, 1);
  const x = (v) => pad + (Math.min(v, top) / top) * (W - pad * 2);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Range ${format(p10)} to ${format(p90)}, median ${format(p50)}`}>
      <line x1={pad} x2={W - pad} y1={20} y2={20} stroke={RULE} strokeWidth="2" />
      <rect x={x(p10)} y={13} width={Math.max(x(p90) - x(p10), 2)} height={14} rx="2" fill="var(--accent-soft)" />
      <line x1={x(p50)} x2={x(p50)} y1={9} y2={31} stroke="var(--accent)" strokeWidth="3" />
      {marker != null && (
        <g>
          <line x1={x(marker)} x2={x(marker)} y1={6} y2={34} stroke={INK} strokeDasharray="3 2" />
          <text x={x(marker)} y={50} fontSize="11" textAnchor="middle" fill={INK}>{markerLabel}</text>
        </g>
      )}
      <text x={x(p10)} y={46} fontSize="11" textAnchor="middle" fill={MUTED}>{format(p10)}</text>
      <text x={x(p90)} y={46} fontSize="11" textAnchor="middle" fill={MUTED}>{format(p90)}</text>
    </svg>
  );
}

// Diverging bars in percentage points around zero.
export function DriverBars({ drivers }) {
  if (!drivers?.length) return <p className="muted">This project looks like a typical request in its region.</p>;
  const maxAbs = Math.max(2, ...drivers.map((d) => Math.abs(d.effect_pp)));
  return (
    <table className="drivers">
      <tbody>
        {drivers.map((d) => {
          const w = (Math.abs(d.effect_pp) / maxAbs) * 50;
          const pos = d.effect_pp >= 0;
          return (
            <tr key={d.factor}>
              <th scope="row">
                {d.factor}
                <span className="sub">{d.yours} <span className="vs">vs typical {d.typical}</span></span>
              </th>
              <td className="bar-cell">
                <div className="diverge">
                  <span className="axis" />
                  <span
                    className={pos ? "seg pos" : "seg neg"}
                    style={pos ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
                  />
                </div>
              </td>
              <td className={`num ${pos ? "good" : "bad"}`}>
                {pos ? "+" : "−"}{Math.abs(d.effect_pp).toFixed(1)} pts
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// Simple labelled horizontal bars.
export function HBars({ rows, format, max }) {
  const top = max ?? Math.max(...rows.map((r) => r.value ?? 0), 1e-9);
  return (
    <table className="hbars">
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            <td className="bar-cell">
              <span className="hbar" style={{ width: `${((r.value ?? 0) / top) * 100}%`, background: r.color }} />
            </td>
            <td className="num">{format(r.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Stacked vertical bars, e.g. GW entering the queue each year by technology.
export function StackedColumns({ data, keys, colors, labels, height = 220, yLabel }) {
  const W = 640;
  const H = height;
  const left = 40;
  const bottom = 24;
  const totals = data.map((d) => keys.reduce((s, k) => s + (d[k] || 0), 0));
  const top = Math.max(...totals, 1);
  const bw = (W - left - 8) / data.length;
  const y = (v) => (H - bottom) - (v / top) * (H - bottom - 10);
  const ticks = [0, top / 2, top];
  return (
    <figure className="figure">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={yLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke={RULE} />
            <text x={left - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill={MUTED}>{Math.round(t)}</text>
          </g>
        ))}
        {data.map((d, i) => {
          let acc = 0;
          return (
            <g key={d.year}>
              {keys.map((k) => {
                const v = d[k] || 0;
                const y0 = y(acc);
                acc += v;
                return <rect key={k} x={left + i * bw + 1} width={bw - 2} y={y(acc)} height={y0 - y(acc)} fill={colors[k]}>
                  <title>{`${d.year} ${labels[k]}: ${v.toFixed(1)}`}</title>
                </rect>;
              })}
              {(i % 4 === 0 || i === data.length - 1) && (
                <text x={left + i * bw + bw / 2} y={H - 6} fontSize="11" textAnchor="middle" fill={MUTED}>{d.year}</text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="legend">
        {yLabel && <span className="muted">{yLabel} · </span>}
        {keys.map((k) => (
          <span key={k}><i style={{ background: colors[k] }} />{labels[k]}</span>
        ))}
      </figcaption>
    </figure>
  );
}

// Line over years.
export function YearLine({ data, xKey, yKey, height = 180, format, yLabel }) {
  const pts = data.filter((d) => d[yKey] != null);
  if (pts.length < 2) return null;
  const W = 640;
  const H = height;
  const left = 40;
  const bottom = 24;
  const xs = pts.map((d) => d[xKey]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const top = Math.max(...pts.map((d) => d[yKey])) * 1.1;
  const x = (v) => left + ((v - x0) / Math.max(x1 - x0, 1)) * (W - left - 12);
  const y = (v) => (H - bottom) - (v / top) * (H - bottom - 10);
  const path = pts.map((d, i) => `${i ? "L" : "M"}${x(d[xKey])},${y(d[yKey])}`).join(" ");
  return (
    <figure className="figure">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={yLabel}>
        {[0, top / 2, top].map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke={RULE} />
            <text x={left - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill={MUTED}>{format(t)}</text>
          </g>
        ))}
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
        {pts.map((d) => (
          <circle key={d[xKey]} cx={x(d[xKey])} cy={y(d[yKey])} r="3" fill="var(--accent)">
            <title>{`${d[xKey]}: ${format(d[yKey])}`}</title>
          </circle>
        ))}
        {pts.filter((_, i) => i % 3 === 0 || i === pts.length - 1).map((d) => (
          <text key={d[xKey]} x={x(d[xKey])} y={H - 6} fontSize="11" textAnchor="middle" fill={MUTED}>{d[xKey]}</text>
        ))}
      </svg>
      {yLabel && <figcaption className="legend muted">{yLabel}</figcaption>}
    </figure>
  );
}

// Predicted vs observed completion rate, by bin.
export function CalibrationPlot({ bins }) {
  const S = 260;
  const pad = 34;
  const top = Math.max(0.2, ...bins.map((b) => Math.max(b.predicted, b.observed))) * 1.05;
  const s = (v) => (v / top) * (S - pad - 10);
  return (
    <svg className="chart square" viewBox={`0 0 ${S} ${S}`} role="img" aria-label="Calibration plot">
      <rect x={pad} y={10} width={S - pad - 10} height={S - pad - 10} fill="none" stroke={RULE} />
      <line x1={pad} y1={S - pad} x2={pad + s(top)} y2={S - pad - s(top)} stroke={MUTED} strokeDasharray="4 3" />
      {bins.map((b, i) => (
        <circle key={i} cx={pad + s(b.predicted)} cy={S - pad - s(b.observed)} r={3 + Math.sqrt(b.n) / 12}
          fill="var(--accent)" fillOpacity="0.75">
          <title>{`predicted ${(b.predicted * 100).toFixed(1)}%, observed ${(b.observed * 100).toFixed(1)}% (n=${b.n})`}</title>
        </circle>
      ))}
      <text x={S / 2 + pad / 2} y={S - 8} fontSize="11" textAnchor="middle" fill={MUTED}>predicted</text>
      <text x={10} y={S / 2} fontSize="11" textAnchor="middle" fill={MUTED} transform={`rotate(-90 10 ${S / 2})`}>observed</text>
    </svg>
  );
}

// Odds vs expected upgrade cost for each candidate substation.
export function SiteScatter({ rows, selected, onPick }) {
  const pts = rows.filter((r) => r.cost_p50_per_kw != null);
  if (!pts.length) return null;
  const W = 640;
  const H = 260;
  const left = 44;
  const bottom = 30;
  const xmax = Math.max(...pts.map((r) => r.cost_p50_per_kw)) * 1.08;
  const ymax = Math.max(...pts.map((r) => r.completion_probability)) * 1.1;
  const x = (v) => left + (v / xmax) * (W - left - 10);
  const y = (v) => (H - bottom) - (v / ymax) * (H - bottom - 10);
  return (
    <figure className="figure">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Completion odds against upgrade cost by substation">
        {[0, ymax / 2, ymax].map((t) => (
          <g key={t}>
            <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke={RULE} />
            <text x={left - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill={MUTED}>{Math.round(t * 100)}%</text>
          </g>
        ))}
        {[0, xmax / 2, xmax].map((t) => (
          <text key={t} x={x(t)} y={H - 10} fontSize="11" textAnchor="middle" fill={MUTED}>${Math.round(t)}</text>
        ))}
        {pts.map((r) => {
          const sel = r.substation_id === selected;
          return (
            <circle key={r.substation_id} cx={x(r.cost_p50_per_kw)} cy={y(r.completion_probability)}
              r={sel ? 7 : 5} fill={sel ? "var(--ink)" : r.undersized ? "var(--muted)" : "var(--accent)"}
              fillOpacity={sel ? 1 : 0.7} stroke={sel ? "var(--paper)" : "none"} strokeWidth="2"
              style={{ cursor: "pointer" }} onClick={() => onPick?.(r)}>
              <title>{`${r.name}: ${(r.completion_probability * 100).toFixed(1)}%, ~$${r.cost_p50_per_kw}/kW`}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption className="legend muted">
        Up and to the left is better: higher odds, cheaper upgrades. Dark dot = your current pick; grey = undersized for this project. Click a dot to assess it.
      </figcaption>
    </figure>
  );
}
