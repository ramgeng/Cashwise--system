import { useEffect, useState } from "react";
import { api } from "./api.js";
import Chat from "./components/Chat.jsx";
import ForecastChart from "./components/ForecastChart.jsx";
import Headline from "./components/Headline.jsx";
import SidePanel from "./components/SidePanel.jsx";
import { longDay, inr } from "./format.js";

export default function App() {
  const [memory, setMemory] = useState(true);
  const [biz, setBiz] = useState(null);
  const [fc, setFc] = useState(null);
  const [customers, setCustomers] = useState(null);
  const [bills, setBills] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.business(), api.forecast(), api.customers(), api.bills()])
      .then(([b, f, c, bl]) => { setBiz(b); setFc(f); setCustomers(c); setBills(bl); })
      .catch((e) => setError(`${e.message}. Is the API running? Start it with: uvicorn app.api:app --reload`));
  }, []);

  return (
    <div className={`app ${memory ? "mem-on" : "mem-off"}`}>
      <header className="top">
        <div>
          <p className="brand">CashFlow Intelligence</p>
          {biz && <p className="biz">{biz.name}, {biz.city}. Cash today {inr(biz.cash)}, {longDay(biz.as_of)}</p>}
        </div>
        <label className="switch">
          <input type="checkbox" checked={memory} onChange={(e) => setMemory(e.target.checked)} />
          <span className="track" aria-hidden="true"><span className="thumb" /></span>
          <span className="switch-label">Memory {memory ? "on" : "off"}</span>
        </label>
      </header>

      {error && <p className="error banner">{error}</p>}

      {fc && (
        <main>
          <Headline data={fc} memory={memory} />
          <ForecastChart data={fc} memory={memory} />
          <div className="lower">
            <Chat memory={memory} />
            <SidePanel customers={customers} bills={bills} memory={memory} />
          </div>
          <footer className="assumptions">
            <h2>How this forecast works</h2>
            <ul>
              {(memory ? fc.assumptions : ["Every open invoice is paid in full on its due date",
                ...fc.assumptions.slice(1)]).map((a) => <li key={a}>{a}</li>)}
            </ul>
          </footer>
        </main>
      )}
      {!fc && !error && <p className="loading">Loading your numbers…</p>}
    </div>
  );
}
