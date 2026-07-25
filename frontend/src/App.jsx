import { useState } from "react";
import { assessSite } from "./api";

function App() {
  const [region, setRegion] = useState("PJM");
  const [technology, setTechnology] = useState("solar");
  const [capacity, setCapacity] = useState(150);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    setError(null);
    try {
      const response = await assessSite({
        region,
        technology,
        capacity_mw: Number(capacity),
      });

      setResult(response);
    } catch (err) {
      console.error(err);
      setError(err.message || String(err));
    }
  };

  return (
    <div>
      <h1>Grid Interconnection Risk Analyzer</h1>

      <label>ISO Region</label>
      <select
        value={region}
        onChange={(e) => setRegion(e.target.value)}
      >
        <option>PJM</option>
        <option>MISO</option>
        <option>SPP</option>
        <option>ERCOT</option>
      </select>

      <br />
      <br />

      <label>Technology</label>
      <select
        value={technology}
        onChange={(e) => setTechnology(e.target.value)}
      >
        <option>solar</option>
        <option>wind</option>
        <option>storage</option>
        <option>hybrid</option>
      </select>

      <br />
      <br />

      <label>Capacity MW</label>
      <input
        type="number"
        value={capacity}
        onChange={(e) => setCapacity(e.target.value)}
      />

      <br />
      <br />

      <button onClick={handleAnalyze}>
        Analyze Site
      </button>

      {result && (
        <div>
          <h2>Assessment Result</h2>

          <p>
            Risk Score: {result.risk_score}
          </p>

          <p>
            Risk Level: {result.risk_level}
          </p>
        </div>
      )}
      {error && (
        <div style={{ color: "red" }}>
          <h3>API Error</h3>
          <pre>{error}</pre>
        </div>
      )}
    </div>
  );
}

export default App;