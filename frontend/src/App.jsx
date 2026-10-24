import { useEffect, useState } from "react";
import { api } from "./api";
import { DEFAULT_INPUT } from "./input";
import AssessView from "./views/AssessView";
import CompareView from "./views/CompareView";
import MarketView from "./views/MarketView";
import ModelView from "./views/ModelView";
import PortfolioView from "./views/PortfolioView";

const TABS = [
  { id: "assess", label: "Assess" },
  { id: "compare", label: "Compare sites" },
  { id: "portfolio", label: "Portfolio" },
  { id: "market", label: "Market" },
  { id: "model", label: "Model" },
];

function initialTab() {
  const h = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === h) ? h : "assess";
}

export default function App() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTabState] = useState(initialTab);
  const [input, setInput] = useState(DEFAULT_INPUT);

  const setTab = (id) => {
    setTabState(id);
    window.history.replaceState(null, "", `#${id}`);
  };

  // Poll until the backend has finished seeding and training.
  useEffect(() => {
    let timer;
    let live = true;
    const poll = () =>
      api.meta()
        .then((m) => {
          if (!live) return;
          setMeta(m);
          setError(null);
          if (m.status !== "ready" && m.status !== "error") timer = setTimeout(poll, 2000);
        })
        .catch((e) => {
          if (!live) return;
          setError(e.message);
          timer = setTimeout(poll, 3000);
        });
    poll();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);

  const ready = meta?.status === "ready";

  return (
    <>
      <header className="masthead">
        <div className="brand">
          <strong>Grid Risk</strong>
          <span>Interconnection queue screening</span>
        </div>
        <nav aria-label="Sections">
          {TABS.map((t) => (
            <button key={t.id} type="button" className={tab === t.id ? "tab on" : "tab"}
              aria-current={tab === t.id ? "page" : undefined} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {error && !meta && <p className="error">Can’t reach the API: {error}</p>}
        {meta && !ready && (
          <p className="notice">
            {meta.status === "error"
              ? `Model failed to load: ${meta.error}`
              : "Preparing data and training models. The first start takes about a minute…"}
          </p>
        )}
        {ready && tab === "assess" && (
          <AssessView meta={meta} input={input} setInput={setInput} onCompare={() => setTab("compare")} />
        )}
        {ready && tab === "compare" && (
          <CompareView meta={meta} input={input} setInput={setInput} onAssess={() => setTab("assess")} />
        )}
        {ready && tab === "portfolio" && <PortfolioView />}
        {ready && tab === "market" && <MarketView meta={meta} />}
        {ready && tab === "model" && <ModelView />}
      </main>

      <footer>
        Screening estimates, not interconnection studies. Data as of {meta?.data_cutoff ?? "…"}.
      </footer>
    </>
  );
}
