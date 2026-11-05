import { useState } from "react";
import { api } from "../api.js";
import { day, inr, money, monthYear } from "../format.js";

export function Customers({ list }) {
  return (
    <ul className="rows">
      {list.map((c) => {
        const delays = (c.recent_invoices || []).map((r) => r.days_late).reverse();
        const max = Math.max(20, ...delays.map(Math.abs));
        const slower = c.quarterly_trend?.startsWith("getting slower") || c.recent_change === "slower lately";
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
                {slower && <span className="tag tag-warn">getting slower</span>}
              </span>
              <span className="spark" aria-label={`Last ${delays.length} invoices: ${delays.join(", ")} days late`}>
                {delays.map((d, i) => (
                  <i key={i} style={{ height: `${Math.max(3, (Math.max(d, 0) / max) * 24)}px` }}
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

export function Bills({ data }) {
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

const TYPE_LABEL = {
  collection_attempt: "Collection", dispute: "Dispute", dispute_resolved: "Dispute settled",
  extension_request: "Extension", late_payment_penalty: "Late fee", early_payment_discount: "Discount",
  decision: "Owner decision", preference: "Owner preference", capital_infusion: "Owner action",
  customer_note: "Customer note", new_customer: "New customer", recommendation: "Agent advice",
  feedback: "Your feedback", outcome: "Outcome",
};

function Timeline({ data, lessonsOnly }) {
  const items = data.items.filter((i) => !lessonsOnly || i.lesson);
  let month = "";
  return (
    <ol className="timeline">
      {items.map((it, idx) => {
        const m = monthYear(it.date);
        const head = m !== month ? (month = m) : null;
        return (
          <li key={idx} className={`tl ${it.lesson ? "tl-lesson" : ""} ${it.live ? "tl-live" : ""}`}>
            {head && <p className="tl-month">{head}</p>}
            <div className="tl-body">
              <p className="tl-meta">
                <span>{day(it.date)}</span>
                <span className="tl-type">{TYPE_LABEL[it.type] || it.type}</span>
                <span>{it.who}</span>
                {it.live && <span className="tag tag-live">learned today</span>}
              </p>
              <p className="tl-text">{money(it.text)}</p>
              {it.outcome && <p className="tl-outcome">{money(it.outcome)}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function Memory({ memory, timeline, onSaved }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [outcome, setOutcome] = useState("");
  const [saved, setSaved] = useState("");
  const [lessonsOnly, setLessonsOnly] = useState(true);
  const [searching, setSearching] = useState(false);

  if (!memory) return <p className="empty">Memory is off. Turn it on to see everything the agent has learned.</p>;

  async function search(e) {
    e.preventDefault();
    setErr(""); setSearching(true);
    try { setRes(await api.memories(q || "important patterns, decisions and preferences")); }
    catch (e2) { setErr(e2.message); }
    finally { setSearching(false); }
  }
  async function record(e) {
    e.preventDefault();
    try {
      await api.outcome(outcome);
      setSaved("Outcome saved. Future advice will take it into account.");
      setOutcome("");
      onSaved();
    } catch (e2) { setSaved(e2.message); }
  }

  return (
    <div className="memory">
      <form onSubmit={search} className="inline">
        <label htmlFor="mq" className="sr-only">Search memory</label>
        <input id="mq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="What worked with Mehta Traders?" />
        <button type="submit" disabled={searching}>{searching ? "Searching" : "Search"}</button>
      </form>
      {err && <p className="error">{err}</p>}
      {res && (
        <div className="recall">
          {res.memories.length ? res.memories.map((m, i) => <p key={i} className="mem">{money(m)}</p>)
            : <p className="empty">Nothing remembered about that yet.</p>}
        </div>
      )}

      <details className="record">
        <summary>Record what happened</summary>
        <form onSubmit={record} className="stack">
          <label htmlFor="oc" className="sr-only">What happened</label>
          <textarea id="oc" rows={2} value={outcome} onChange={(e) => setOutcome(e.target.value)}
            placeholder="Called Mehta on 7 Nov, INV-1179 paid on 9 Nov" />
          <button type="submit" disabled={!outcome.trim()}>Save outcome</button>
        </form>
        {saved && <p className="saved">{saved}</p>}
      </details>

      <div className="tl-head">
        <h3>What the agent remembers</h3>
        <label className="check">
          <input type="checkbox" checked={lessonsOnly} onChange={(e) => setLessonsOnly(e.target.checked)} />
          Lessons only
        </label>
      </div>
      {timeline ? (
        <>
          <p className="tl-count">
            {timeline.counts.history} events from the past year
            {timeline.counts.learned_live ? `, ${timeline.counts.learned_live} learned today` : ""}
          </p>
          <Timeline data={timeline} lessonsOnly={lessonsOnly} />
        </>
      ) : <div className="skeleton" />}
    </div>
  );
}

export default function SidePanel({ customers, bills, memory, timeline, onSaved }) {
  const [tab, setTab] = useState("customers");
  const tabs = [["customers", "Who owes you"], ["bills", "What you owe"], ["memory", "Memory"]];
  return (
    <section className="side card" aria-label="Details">
      <div role="tablist" className="tabs">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      <div role="tabpanel" className="tabpanel">
        {tab === "customers" && (customers ? <Customers list={customers} /> : <div className="skeleton" />)}
        {tab === "bills" && (bills ? <Bills data={bills} /> : <div className="skeleton" />)}
        {tab === "memory" && <Memory memory={memory} timeline={timeline} onSaved={onSaved} />}
      </div>
    </section>
  );
}
