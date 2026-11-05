import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import DataPage, { Onboarding } from "./components/DataPage.jsx";
import { ActionsCard, BalanceCard, Card, ForecastHero, PayablesCard, PositionCard, ReceivablesCard } from "./components/Cards.jsx";
import Chat from "./components/Chat.jsx";
import ForecastChart from "./components/ForecastChart.jsx";
import AlertsPage, { alertCount } from "./components/Alerts.jsx";
import ReportsPage from "./components/Reports.jsx";
import { Sidebar, Topbar } from "./components/Shell.jsx";
import { Bills, Customers, Memory } from "./components/SidePanel.jsx";
import WhatIf, { buildChanges } from "./components/WhatIf.jsx";
import Icon from "./icons.jsx";

const START_W = { customer: "C001", delay: 0, payNow: null, collections: 0, pinned: [] };

export default function Dashboard({ user, businesses, onSwitch, onAdd, onSignOut, dark, setDark }) {
  const [view, setView] = useState("overview");
  const [memory, setMemory] = useState(true);
  const [biz, setBiz] = useState(null);
  const [fc, setFc] = useState(null);
  const [actions, setActions] = useState(null);
  const [position, setPosition] = useState(null);
  const [smart, setSmart] = useState(null);
  const loadAlerts = useCallback(() => { api.alerts().then(setSmart).catch(() => setSmart(null)); }, []);
  const [customers, setCustomers] = useState(null);
  const [bills, setBills] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState("");
  const askRef = useRef(null);

  const [w, setW] = useState(START_W);
  const [scenario, setScenario] = useState(null);
  const [wiBusy, setWiBusy] = useState(false);
  const [wiError, setWiError] = useState("");

  const refreshTimeline = useCallback(() => { api.timeline().then(setTimeline).catch(() => {}); }, []);

  // Load (or reload, after an upload) everything the dashboard shows for this business.
  const load = useCallback(() => {
    setError("");
    return Promise.all([api.business(), api.forecast(), api.customers(), api.bills()])
      .then(([b, f, c, bl]) => {
        setBiz(b); setFc(f); setCustomers(c); setBills(bl);
        setW((x) => (c.some((k) => k.customer_id === x.customer) ? x : { ...START_W, customer: c[0]?.customer_id || "" }));
        api.actions().then(setActions).catch(() => setActions({ actions: [] }));
        api.position().then(setPosition).catch(() => setPosition(null));
        loadAlerts();
        refreshTimeline();
      })
      .catch((e) => setError(e.message));
  }, [refreshTimeline, loadAlerts]);
  useEffect(() => { load(); }, [load]);
  const [health, setHealth] = useState(null);
  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  async function loadDemoData() {
    try { await api.loadDemo(); } catch (e) { setError(e.message); return; }
    load();
  }

  // Recalculate the what-if line shortly after the controls stop moving.
  const changes = useMemo(() => buildChanges(w, fc?.key_bill), [w, fc]);
  useEffect(() => {
    if (!changes.length) { setScenario(null); setWiError(""); return; }
    setWiBusy(true);
    const t = setTimeout(() => {
      api.scenario(changes)
        .then((s) => { setScenario(s); setWiError(""); })
        .catch((e) => setWiError(e.message))
        .finally(() => setWiBusy(false));
    }, 280);
    return () => clearTimeout(t);
  }, [changes]);

  function preview(change) {
    if (change.type === "split_bill") {
      setW((x) => ({ ...x, payNow: x.payNow === change.amount ? null : change.amount }));
      return;
    }
    setW((x) => {
      const key = JSON.stringify(change);
      const has = x.pinned.some((p) => JSON.stringify(p) === key);
      return { ...x, pinned: has ? x.pinned.filter((p) => JSON.stringify(p) !== key) : [...x.pinned, change] };
    });
  }
  const previewing = [...w.pinned, ...changes.filter((c) => c.type === "split_bill")];

  const alerts = memory ? actions?.actions?.length || 0 : 0;
  const go = (v) => { setView(v); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const focusAsk = () => { askRef.current?.focus(); askRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); };

  const chart = (h, i) => (
    <Card i={i} className="chart-card">
      <div className="card-head">
        <span className="ic"><Icon name="chart" size={18} /></span>
        <h2>Cash forecast</h2>
      </div>
      <ForecastChart data={fc} memory={memory} scenario={memory ? scenario : null} dark={dark} height={h} />
    </Card>
  );
  const whatIf = (i) => memory ? (
    <Card i={i} className="whatif-card">
      <WhatIf w={w} setW={setW} customers={customers} keyBill={fc.key_bill} scenario={scenario}
        base={fc.summary.likely.on_target} busy={wiBusy} error={wiError} />
    </Card>
  ) : (
    <Card i={i}><p className="empty">Switch memory on to try what-ifs against how customers really pay.</p></Card>
  );

  return (
    <div className="shell">
      <Sidebar view={view} setView={go} alerts={alerts} smartAlerts={alertCount(smart)} user={user} onSignOut={onSignOut} />
      <div className="main">
        <Topbar biz={biz} user={user} businesses={businesses} onSwitch={onSwitch} onAdd={onAdd} onSignOut={onSignOut} view={view} setView={go}
          dark={dark} setDark={setDark} memory={memory} setMemory={setMemory}
          fc={fc} actions={actions} previewing={previewing} onPreview={preview} smart={smart} />
        {error && <p className="error banner">{error}</p>}

        <div className="layout">
          <div className="content" key={view}>
            {!fc || !biz ? (
              <div className="grid">
                <div className="skeleton span-3 sk-tall" /><div className="skeleton span-3 sk-tall" />
                <div className="skeleton span-6 sk-chart" />
              </div>
            ) : view === "data" ? (
              <DataPage biz={biz} onChanged={load} />
            ) : !biz.has_data ? (
              <Onboarding biz={biz} onGo={() => go("data")} onDemo={loadDemoData} />
            ) : view === "overview" ? (
              <div className="grid">
                <div className="span-3"><BalanceCard i={0} biz={biz} fc={fc} onAsk={focusAsk}
                  onRecord={() => go("memory")} onOpenForecast={() => go("forecast")} onChanged={load} /></div>
                <div className="span-3"><ForecastHero i={1} fc={fc} memory={memory} setMemory={setMemory}
                  scenario={changes.length ? scenario : null} busy={wiBusy} onOpenGraph={() => go("forecast")} /></div>
                <div className="span-6"><PositionCard i={2} data={position} /></div>
                <div className="span-2"><ActionsCard i={3} data={actions} memory={memory} previewing={previewing} onPreview={preview} /></div>
                <div className="span-2"><ReceivablesCard i={4} fc={fc} customers={customers} onOpen={() => go("customers")} /></div>
                <div className="span-2"><PayablesCard i={5} fc={fc} bills={bills} onOpen={() => go("bills")} /></div>
              </div>
            ) : view === "reports" ? (
              <ReportsPage biz={biz} />
            ) : view === "alerts" ? (
              <AlertsPage data={smart} biz={biz} onGo={go} onReload={loadAlerts} />
            ) : view === "forecast" ? (
              <div className="grid">
                <div className="span-6">{chart(380, 0)}</div>
                <div className="span-4">{whatIf(1)}</div>
                <div className="span-2"><ActionsCard i={2} data={actions} memory={memory} previewing={previewing} onPreview={preview} /></div>
                <div className="span-6">
                  <Card i={3}>
                    <div className="card-head"><span className="ic"><Icon name="help" size={18} /></span><h2>How this forecast works</h2></div>
                    <ul className="assume">
                      {(memory ? fc.assumptions : ["Every open invoice is paid in full on its due date", ...fc.assumptions.slice(1)])
                        .map((a) => <li key={a}>{a}</li>)}
                    </ul>
                  </Card>
                </div>
              </div>
            ) : view === "customers" ? (
              <div className="grid">
                <div className="span-2"><ReceivablesCard i={0} fc={fc} customers={customers} onOpen={() => {}} /></div>
                <div className="span-4">
                  <Card i={1}>
                    <div className="card-head"><span className="ic"><Icon name="users" size={18} /></span><h2>Who owes you</h2></div>
                    {customers ? <Customers list={customers} /> : <div className="skeleton" />}
                  </Card>
                </div>
              </div>
            ) : view === "bills" ? (
              <div className="grid">
                <div className="span-2"><PayablesCard i={0} fc={fc} bills={bills} onOpen={() => {}} /></div>
                <div className="span-4">
                  <Card i={1}>
                    <div className="card-head"><span className="ic"><Icon name="receipt" size={18} /></span><h2>What you owe</h2></div>
                    {bills ? <Bills data={bills} /> : <div className="skeleton" />}
                  </Card>
                </div>
              </div>
            ) : (
              <div className="grid">
                <div className="span-6">
                  <Card i={0}>
                    <div className="card-head"><span className="ic"><Icon name="brain" size={18} /></span><h2>Memory</h2></div>
                    <Memory memory={memory} timeline={timeline} onSaved={refreshTimeline} />
                  </Card>
                </div>
              </div>
            )}
          </div>

          <Chat memory={memory} onSaved={refreshTimeline} owner={(user?.name || biz?.owner || "there").split(" ")[0]} inputRef={askRef}
            demo={!!biz?.is_demo} memoryReady={health ? health.memory_configured : true} />
        </div>
      </div>
    </div>
  );
}
