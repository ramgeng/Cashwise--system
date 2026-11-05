import { useState } from "react";
import { api } from "../api.js";
import { day, inr } from "../format.js";

function Customers({ list }) {
  return (
    <ul className="rows">
      {list.map((c) => {
        const delays = (c.recent_invoices || []).map((r) => r.days_late).reverse();
        const max = Math.max(20, ...delays.map(Math.abs));
        return (
          <li key={c.customer_id} className="row">
            <div className="row-main">
              <strong>{c.name}</strong>
              <span className="amount">{c.open_total ? inr(c.open_total) : "Nothing owed"}</span>
            </div>
            <div className="row-sub">
              <span>
                {c.paid_invoices
                  ? c.median_days_late <= 0 ? "Usually pays on time" : `Usually ${c.median_days_late} days late`
                  : "New, no history yet"}
                {c.pays_in_instalments ? ", pays in halves" : ""}
                {c.quarterly_trend?.startsWith("getting slower") ? ", getting slower" : ""}
                {c.recent_change === "slower lately" ? ", slower lately" : ""}
              </span>
              <span className="spark" aria-label={`Last ${delays.length} invoices: ${delays.join(", ")} days late`}>
                {delays.map((d, i) => (
                  <i key={i} style={{ height: `${Math.max(3, (Math.max(d, 0) / max) * 22)}px` }}
                    className={d > 7 ? "late" : ""} />
                ))}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Bills({ data }) {
  return (
    <>
      <ul className="rows">
        {data.bills.map((b) => (
          <li key={b.bill_id} className="row">
            <div className="row-main">
              <strong>{b.supplier}</strong>
              <span className="amount">{inr(b.amount)}</span>
            </div>
            <div className="row-sub">
              <span>Due {day(b.due)}</span>
              <span>
                {b.early_pay_discount_pct > 0 && `${b.early_pay_discount_pct}% off if paid early`}
                {b.late_fee_pct_per_month > 0 && `${b.late_fee_pct_per_month}% monthly late fee`}
              </span>
            </div>
          </li>
        ))}
      </ul>
      <p className="total">Total due {inr(data.bills.reduce((s, b) => s + b.amount, 0))}</p>
    </>
  );
}

function Memory({ memory }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [outcome, setOutcome] = useState("");
  const [saved, setSaved] = useState("");

  if (!memory) return <p className="empty">Memory is off. Turn it on to see what the agent remembers.</p>;

  async function search(e) {
    e.preventDefault();
    setErr("");
    try { setRes(await api.memories(q || "important patterns, decisions and preferences")); }
    catch (e2) { setErr(e2.message); }
  }
  async function record(e) {
    e.preventDefault();
    try { await api.outcome(outcome); setSaved("Outcome saved. Future forecasts and advice will use it."); setOutcome(""); }
    catch (e2) { setSaved(e2.message); }
  }

  return (
    <div className="memory">
      <form onSubmit={search} className="inline">
        <label htmlFor="mq" className="sr-only">Search memory</label>
        <input id="mq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="What worked with Mehta Traders?" />
        <button type="submit">Search</button>
      </form>
      {err && <p className="error">{err}</p>}
      {res && (res.memories.length ? res.memories.map((m, i) => <p key={i} className="mem">{m}</p>)
        : <p className="empty">Nothing remembered about that yet.</p>)}

      <form onSubmit={record} className="stack">
        <label htmlFor="oc">Record what happened</label>
        <textarea id="oc" rows={2} value={outcome} onChange={(e) => setOutcome(e.target.value)}
          placeholder="Called Mehta on 7 Nov, INV-1179 paid on 9 Nov" />
        <button type="submit" disabled={!outcome.trim()}>Save outcome</button>
      </form>
      {saved && <p className="saved">{saved}</p>}
    </div>
  );
}

export default function SidePanel({ customers, bills, memory }) {
  const [tab, setTab] = useState("customers");
  const tabs = [["customers", "Who owes you"], ["bills", "What you owe"], ["memory", "Memory"]];
  return (
    <section className="side" aria-label="Details">
      <div role="tablist" className="tabs">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "customers" && (customers ? <Customers list={customers} /> : <p className="empty">Loading…</p>)}
        {tab === "bills" && (bills ? <Bills data={bills} /> : <p className="empty">Loading…</p>)}
        {tab === "memory" && <Memory memory={memory} />}
      </div>
    </section>
  );
}
