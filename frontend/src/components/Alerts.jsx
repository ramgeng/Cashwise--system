import { useEffect, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { day, inr, money } from "../format.js";
import { Card } from "./Cards.jsx";

/*
  Smart alerts: unusual expenses, low cash warnings and cash-flow risks.
  Everything is worked out by the backend from the books and the forecast, so each number can be checked.
  Hidden alerts are remembered per business in this browser.
*/
const GROUPS = [
  { key: "cash", label: "Low cash", title: "Low cash balance warnings", icon: "wallet",
    blurb: "When the bank balance is likely to drop below zero or below your safety buffer." },
  { key: "risk", label: "Cash-flow risks", title: "Potential cash-flow risks", icon: "alert",
    blurb: "Things that could leave you short: slow payers, money stuck overdue, bills you can't cover." },
  { key: "expense", label: "Unusual expenses", title: "Unusual expense alerts", icon: "receipt",
    blurb: "Expenses much bigger than usual for their category, new or one-off costs, and heavy months." },
];
const SEV = { critical: "Act now", warning: "Watch", info: "Good to know" };
const SEV_ICON = { critical: "alert", warning: "bell", info: "help" };
const VIEW_LABEL = { forecast: "See forecast", customers: "See customers", bills: "See bills", overview: "See actions",
  data: "See expenses" };

const hiddenKey = (id) => `cashwise-hidden-alerts-${id}`;
const readHidden = (id) => { try { return JSON.parse(localStorage.getItem(hiddenKey(id)) || "[]"); } catch { return []; } };
const writeHidden = (id, v) => { try { localStorage.setItem(hiddenKey(id), JSON.stringify(v)); } catch { /* ignore */ } };

export function alertCount(data) {
  return data ? (data.counts?.critical || 0) + (data.counts?.warning || 0) : 0;
}

function AlertRow({ a, onGo, onHide, hidden }) {
  return (
    <li className={`al-row sev-${a.severity} ${hidden ? "is-hidden" : ""}`}>
      <span className="al-ic"><Icon name={SEV_ICON[a.severity]} size={17} /></span>
      <div className="al-text">
        <div className="al-top">
          <span className="al-sev">{SEV[a.severity]}</span>
          {a.date && <span className="al-date">{day(a.date)}</span>}
        </div>
        <p className="al-title">{money(a.title)}</p>
        <p className="al-detail">{money(a.detail)}</p>
      </div>
      <div className="al-btns">
        {a.view && <button className="btn-mini magnet" onClick={() => onGo(a.view)}>{VIEW_LABEL[a.view] || "Open"}</button>}
        <button className="al-hide" onClick={() => onHide(a.id)} title={hidden ? "Show again" : "Hide this alert"}
          aria-label={hidden ? "Show again" : "Hide this alert"}>
          <Icon name={hidden ? "eye" : "x"} size={15} stroke={2.4} />
        </button>
      </div>
    </li>
  );
}

function Threshold({ data, onSaved }) {
  const [edit, setEdit] = useState(false);
  const [v, setV] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { setV(String(data.low_cash_threshold || "")); }, [data.low_cash_threshold]);

  async function save(body) {
    setBusy(true); setErr("");
    try { await api.updateBusiness(body); setEdit(false); onSaved(); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  const auto = data.low_cash_basis !== "set by you";

  if (!edit) {
    return (
      <div className="al-buffer">
        <span>Safety buffer <strong>{inr(data.low_cash_threshold)}</strong> <em>({data.low_cash_basis})</em></span>
        <button className="link" onClick={() => setEdit(true)}>Change</button>
      </div>
    );
  }
  return (
    <form className="al-buffer is-edit" onSubmit={(e) => {
      e.preventDefault();
      const n = Math.round(Number(v));
      if (!Number.isFinite(n) || n < 0) { setErr("Enter an amount in rupees, like 400000."); return; }
      if (n > 1e11) { setErr("That's more than ₹1,000 crore. Check the number."); return; }
      save({ low_cash_threshold: n });
    }}>
      <label>Warn me when cash drops below ₹
        <input type="number" min="0" step="10000" value={v} onChange={(e) => setV(e.target.value)} autoFocus />
      </label>
      <button className="btn-mini" disabled={busy}>Save</button>
      {!auto && <button type="button" className="link" disabled={busy} onClick={() => save({ clear_low_cash_threshold: true })}>Use automatic</button>}
      <button type="button" className="link" onClick={() => setEdit(false)}>Cancel</button>
      {err && <p className="error">{err}</p>}
    </form>
  );
}

export default function AlertsPage({ data, biz, onGo, onReload }) {
  const [filter, setFilter] = useState("all");
  const [hidden, setHidden] = useState([]);
  const [showHidden, setShowHidden] = useState(false);
  useEffect(() => { if (biz?.id) setHidden(readHidden(biz.id)); }, [biz?.id]);

  const toggle = (id) => {
    const next = hidden.includes(id) ? hidden.filter((x) => x !== id) : [...hidden, id];
    setHidden(next); if (biz?.id) writeHidden(biz.id, next);
  };

  if (!data) {
    return <div className="grid"><div className="skeleton span-6 sk-tall" /><div className="skeleton span-6 sk-tall" /></div>;
  }
  const visible = data.alerts.filter((a) => showHidden || !hidden.includes(a.id));
  const hiddenCount = data.alerts.filter((a) => hidden.includes(a.id)).length;
  const groups = GROUPS.filter((g) => filter === "all" || filter === g.key);

  return (
    <div className="grid">
      <div className="span-6">
        <Card i={0} className="al-head">
          <div className="card-head">
            <span className="ic"><Icon name="shield" size={18} /></span>
            <h2>Smart alerts</h2>
            <span className="pos-asof">checked {day(data.as_of)} · next {data.horizon_days} days</span>
          </div>
          <div className="al-sum">
            {["critical", "warning", "info"].map((s) => (
              <div key={s} className={`al-count sev-${s}`}>
                <strong>{data.counts[s]}</strong><span>{SEV[s]}</span>
              </div>
            ))}
          </div>
          <div className="al-filters" role="tablist" aria-label="Filter alerts">
            <button role="tab" aria-selected={filter === "all"} className="pill" onClick={() => setFilter("all")}>
              All <em>{data.alerts.length}</em>
            </button>
            {GROUPS.map((g) => (
              <button key={g.key} role="tab" aria-selected={filter === g.key} className="pill" onClick={() => setFilter(g.key)}>
                {g.label} <em>{data.groups[g.key]}</em>
              </button>
            ))}
            {hiddenCount > 0 && (
              <button className="link al-showhidden" onClick={() => setShowHidden(!showHidden)}>
                {showHidden ? "Hide hidden" : `Show ${hiddenCount} hidden`}
              </button>
            )}
          </div>
        </Card>
      </div>

      {groups.map((g, gi) => {
        const list = visible.filter((a) => a.group === g.key);
        return (
          <div className="span-6" key={g.key}>
            <Card i={gi + 1} className={`al-group al-${g.key}`}>
              <div className="card-head">
                <span className="ic"><Icon name={g.icon} size={18} /></span>
                <div className="al-gh"><h2>{g.title}</h2><p>{g.blurb}</p></div>
                <span className="count">{list.length}</span>
              </div>
              {g.key === "cash" && <Threshold data={data} onSaved={onReload} />}
              {list.length === 0 ? (
                <p className="empty al-empty"><Icon name="check" size={16} stroke={2.6} /> Nothing to flag here.</p>
              ) : (
                <ul className="al-list">
                  {list.map((a) => <AlertRow key={a.id} a={a} onGo={onGo} onHide={toggle} hidden={hidden.includes(a.id)} />)}
                </ul>
              )}
            </Card>
          </div>
        );
      })}
    </div>
  );
}
