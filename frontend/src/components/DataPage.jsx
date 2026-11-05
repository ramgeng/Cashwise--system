import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { inr } from "../format.js";
import { Card } from "./Cards.jsx";

// Upload order matters: invoices need customers, payments need invoices.
const ORDER = ["customers", "invoices", "payments_received", "suppliers", "supplier_bills", "payments_made",
  "expenses", "memory_events"];

function Settings({ biz, onSaved, i }) {
  const [f, setF] = useState({
    opening_cash_balance: biz.opening_cash_balance || "",
    opening_date: biz.opening_date || "",
    as_of_date: biz.as_of_fixed ? biz.as_of : "",
  });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setBusy(true); setMsg("");
    try {
      const body = { opening_cash_balance: Number(f.opening_cash_balance) || 0 };
      if (f.opening_date) body.opening_date = f.opening_date;
      if (f.as_of_date) body.as_of_date = f.as_of_date; else body.clear_as_of_date = true;
      const b = await api.updateBusiness(body);
      setMsg(`Saved. Cash today is now ${inr(b.cash)}.`);
      onSaved();
    } catch (err) { setMsg(err.message); } finally { setBusy(false); }
  }

  return (
    <Card i={i} className="settings">
      <div className="card-head"><span className="ic"><Icon name="wallet" size={18} /></span><h2>Starting point</h2></div>
      <p className="sub">Your bank balance on a start date. Payments in and out after that date build today's cash.</p>
      <form className="form" onSubmit={save}>
        <label>Bank balance (₹)
          <input type="number" inputMode="numeric" placeholder="0" value={f.opening_cash_balance}
            onChange={(e) => setF({ ...f, opening_cash_balance: e.target.value })} />
        </label>
        <label>On this start date
          <input type="date" value={f.opening_date} onChange={(e) => setF({ ...f, opening_date: e.target.value })} />
        </label>
        <label>Forecast from
          <input type="date" value={f.as_of_date} onChange={(e) => setF({ ...f, as_of_date: e.target.value })} />
          <span className="hint">Leave empty to use today's date. Set a date to replay older records as if it were that day.</span>
        </label>
        <button className="btn btn-dark" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        {msg && <p className="saved" role="status">{msg}</p>}
      </form>
    </Card>
  );
}

function UploadRow({ type, count, onDone }) {
  const input = useRef(null);
  const [mode, setMode] = useState("replace");
  const [state, setState] = useState(null);   // {busy} | {ok, res} | {error, errors}
  const [open, setOpen] = useState(false);

  async function send(file) {
    if (!file) return;
    setState({ busy: true });
    try {
      const res = await api.upload(type.kind, file, mode);
      setState({ ok: true, res });
      onDone();
    } catch (err) {
      setState({ error: err.message, errors: err.errors || [] });
    } finally {
      if (input.current) input.current.value = "";
    }
  }

  const required = type.columns.filter((c) => c.required).map((c) => c.name);
  return (
    <li className={`up ${state?.error ? "is-bad" : state?.ok ? "is-ok" : ""}`}>
      <div className="up-main">
        <div className="up-text">
          <p className="up-title">{type.label} <span className="up-count">{count ? `${count} rows` : "empty"}</span></p>
          <p className="up-help">{type.help}</p>
          <button className="link" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Hide" : "Show"} columns</button>
        </div>
        <div className="up-actions">
          <a className="chip-btn" href={api.templateUrl(type.kind)} download>Template</a>
          <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label={`How to add ${type.label}`}>
            <option value="replace">Replace all</option>
            <option value="append">Add or update</option>
          </select>
          <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => send(e.target.files[0])} />
          <button className="btn btn-dark magnet" onClick={() => input.current?.click()} disabled={state?.busy}>
            <Icon name="upload" size={16} /> {state?.busy ? "Checking…" : "Upload CSV"}
          </button>
        </div>
      </div>
      {open && (
        <p className="up-cols">
          Required: <strong>{required.join(", ")}</strong>. Optional: {type.columns.filter((c) => !c.required).map((c) => c.name).join(", ") || "none"}.
          Dates like 2026-11-05 or 05/11/2026; amounts can include ₹ and commas.
        </p>
      )}
      {state?.ok && (
        <div className="up-result" role="status">
          <p><Icon name="check" size={16} /> {state.res.inserted} rows saved. Cash today {inr(state.res.books.cash_today)}, {state.res.books.open_invoices} unpaid invoices, {state.res.books.open_bills} unpaid bills.</p>
          {state.res.memory && <p>{state.res.memory}</p>}
          {state.res.warnings?.map((w) => <p key={w} className="warn">{w}</p>)}
        </div>
      )}
      {state?.error && (
        <div className="up-result bad" role="alert">
          <p>{state.error}</p>
          {state.errors.length > 1 && (
            <table className="err-table">
              <thead><tr><th>Row</th><th>Column</th><th>Value</th><th>Problem</th></tr></thead>
              <tbody>
                {state.errors.slice(0, 12).map((e, k) => (
                  <tr key={k}><td>{e.row}</td><td>{e.column}</td><td>{e.value}</td><td>{e.message}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </li>
  );
}

export default function DataPage({ biz, onChanged }) {
  const [types, setTypes] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.dataTypes().then((t) => setTypes(ORDER.map((k) => t.find((x) => x.kind === k)).filter(Boolean))); }, []);

  async function demo() {
    if (biz.has_data && !window.confirm("Replace this business's records with the demo data?")) return;
    setBusy("demo"); setMsg("");
    try { const r = await api.loadDemo(); setMsg(`Demo data loaded. ${r.memory}`); onChanged(); }
    catch (e) { setMsg(e.message); } finally { setBusy(""); }
  }
  async function sync() {
    setBusy("sync"); setMsg("");
    try { const r = await api.syncMemory(); setMsg(r.memory); } catch (e) { setMsg(e.message); } finally { setBusy(""); }
  }

  return (
    <div className="grid">
      <div className="span-4">
        <Card i={0}>
          <div className="card-head"><span className="ic"><Icon name="receipt" size={18} /></span><h2>Upload your records</h2></div>
          <p className="sub">One CSV per type, in this order. Nothing is saved unless every row passes the checks, and you'll see exactly which rows to fix.</p>
          {types ? (
            <ol className="uploads">
              {types.map((t) => <UploadRow key={t.kind} type={t} count={biz.counts?.[t.kind] || 0} onDone={onChanged} />)}
            </ol>
          ) : <div className="skeleton" />}
        </Card>
      </div>
      <div className="span-2 stack-col">
        <Settings biz={biz} onSaved={onChanged} i={1} />
        <Card i={2}>
          <div className="card-head"><span className="ic"><Icon name="brain" size={18} /></span><h2>Memory</h2></div>
          <p className="sub">History events go to this business's own Hindsight memory bank. Re-send them if memory was set up after you uploaded.</p>
          <button className="btn btn-line" onClick={sync} disabled={!!busy || !biz.has_memory_history}>
            {busy === "sync" ? "Sending…" : "Send history to memory"}
          </button>
        </Card>
        <Card i={3}>
          <div className="card-head"><span className="ic"><Icon name="sparkle" size={18} /></span><h2>Demo data</h2></div>
          <p className="sub">Fill this business with a year of records for Malabar Electronics, to try everything out.</p>
          <button className="btn btn-line" onClick={demo} disabled={!!busy}>{busy === "demo" ? "Loading…" : "Load demo data"}</button>
        </Card>
        {msg && <p className="saved" role="status">{msg}</p>}
      </div>
    </div>
  );
}

// Shown on the overview while a business has no invoices or bills yet.
export function Onboarding({ biz, onGo, onDemo }) {
  const steps = [
    ["Set your starting point", "Your bank balance on a start date.", biz.opening_cash_balance > 0],
    ["Add customers, invoices and payments", "So Cashwise learns how each customer pays.", biz.counts?.invoices > 0],
    ["Add suppliers and bills", "So it knows what you have to pay, and when.", biz.counts?.supplier_bills > 0],
    ["Add history for memory", "Calls, disputes, extensions, decisions: what worked before.", biz.counts?.memory_events > 0],
  ];
  return (
    <div className="grid">
      <div className="span-6">
        <Card i={0} className="onboard">
          <div className="onboard-head">
            <div>
              <h1>Let's set up {biz.name}</h1>
              <p className="sub">Four quick uploads, then your forecast and the agent are ready.</p>
            </div>
          </div>
          <ol className="steps">
            {steps.map(([title, help, done], k) => (
              <li key={title} className={done ? "is-done" : ""}>
                <span className="step-dot">{done ? <Icon name="check" size={16} stroke={2.6} /> : k + 1}</span>
                <div><p className="act-title">{title}</p><p className="act-detail">{help}</p></div>
              </li>
            ))}
          </ol>
          <div className="bal-actions">
            <button className="btn btn-dark magnet" onClick={onGo}><Icon name="upload" size={16} /> Upload your data</button>
            <button className="btn btn-line magnet" onClick={onDemo}>Try with demo data</button>
          </div>
        </Card>
      </div>
    </div>
  );
}
