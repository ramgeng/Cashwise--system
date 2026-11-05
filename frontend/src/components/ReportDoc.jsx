import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { day, inr, leftOrShort, longDay, money, when } from "../format.js";

/*
  A report as a document: the same layout on screen, on paper, and on the public read-only link.
  It always looks like paper (dark ink on white), whatever the app's theme, so what you print is what you see.
*/
const signed = (n) => (n == null ? "–" : inr(n, { signed: true }));
const pct = (n) => (n == null ? "–" : `${n}%`);

function Head({ rep }) {
  const d = rep.data;
  return (
    <header className="rd-head">
      <div className="rd-brand">
        <img src="/logo-light.png" alt="" width="40" height="40" />
        <div><strong>Cashwise</strong><span>Cash-flow report</span></div>
      </div>
      <div className="rd-meta">
        <h1>{rep.title}</h1>
        <p>{d.business.name}{d.business.city ? `, ${d.business.city}` : ""}</p>
        <p className="rd-small">Figures as of {longDay(d.as_of)} · made {when(rep.created_at)}{rep.created_by ? ` by ${rep.created_by.split(" (")[0]}` : ""}</p>
      </div>
    </header>
  );
}

function Kpi({ label, value, note, tone }) {
  return (
    <div className={`rd-kpi ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <em>{note}</em>}
    </div>
  );
}

function SummaryBody({ d }) {
  const f = d.flow.likely;
  const p = d.position;
  return (
    <>
      <section className="rd-kpis">
        <Kpi label="Cash in bank" value={inr(d.cash)} note={`on ${day(d.as_of)}`} />
        <Kpi label={`Net cash flow, next ${d.horizon_days} days`} value={signed(f.net)} tone={f.net < 0 ? "neg" : "pos"}
          note={`${inr(f.in)} in · ${inr(f.out)} out (likely)`} />
        <Kpi label="Net position" value={inr(p.net_position)} tone={p.net_position < 0 ? "neg" : "pos"}
          note="cash + owed to you − you owe" />
        <Kpi label="Alerts" value={`${d.alert_counts.critical} urgent`} tone={d.alert_counts.critical ? "neg" : ""}
          note={`${d.alert_counts.warning} to watch`} />
      </section>

      {d.key_bill && (
        <p className="rd-callout">
          After paying <strong>{d.key_bill.supplier} {inr(d.key_bill.amount)}</strong> on {longDay(d.target_date)}:
          likely <strong className={d.on_target.likely < 0 ? "neg" : "pos"}>{leftOrShort(d.on_target.likely)}</strong>.
          A due-date view would say {leftOrShort(d.on_target.naive)}.
        </p>
      )}

      <section className="rd-sec">
        <h2>Cash flow, next {d.horizon_days} days (to {day(d.horizon_end)})</h2>
        <table className="rd-table">
          <thead><tr><th /><th>Best case</th><th>Likely</th><th>Worst case</th></tr></thead>
          <tbody>
            <tr><td>Money coming in</td>{["best", "likely", "worst"].map((k) => <td key={k}>{inr(d.flow[k].in)}</td>)}</tr>
            <tr><td>Money going out</td>{["best", "likely", "worst"].map((k) => <td key={k}>{inr(d.flow[k].out)}</td>)}</tr>
            <tr className="rd-strong"><td>Net cash flow</td>{["best", "likely", "worst"].map((k) => <td key={k} className={d.flow[k].net < 0 ? "neg" : ""}>{signed(d.flow[k].net)}</td>)}</tr>
            <tr><td>Cash at the end</td>{["best", "likely", "worst"].map((k) => <td key={k} className={d.flow[k].closing < 0 ? "neg" : ""}>{inr(d.flow[k].closing)}</td>)}</tr>
            <tr><td>Lowest point</td>{["best", "likely", "worst"].map((k) => <td key={k} className={d.lowest[k].amount < 0 ? "neg" : ""}>{inr(d.lowest[k].amount)} <em>{day(d.lowest[k].date)}</em></td>)}</tr>
          </tbody>
        </table>
        <p className="rd-note">Based on how each customer has actually paid (their last 8 invoices), not on due dates.</p>
      </section>

      <section className="rd-sec">
        <h2>Financial position</h2>
        <table className="rd-table rd-two">
          <tbody>
            <tr><td>Cash in bank</td><td>{inr(p.cash)}</td></tr>
            <tr><td>Owed to you{p.receivable_overdue ? ` (${inr(p.receivable_overdue)} overdue)` : ""}</td><td>+ {inr(p.receivable)}</td></tr>
            <tr><td>You owe ({inr(p.payable_30)} within 30 days)</td><td>− {inr(p.payable)}</td></tr>
            <tr className="rd-strong"><td>Net position</td><td className={p.net_position < 0 ? "neg" : "pos"}>{inr(p.net_position)}</td></tr>
            <tr><td>Cover (cash + owed to you, per ₹1 you owe)</td><td>{p.cover == null ? "–" : `${p.cover.toFixed(2)}×`}</td></tr>
            <tr><td>Last 30 days, actual</td><td>{signed(p.last_30.net)} <em>({inr(p.last_30.in)} in, {inr(p.last_30.out)} out)</em></td></tr>
            <tr><td>Running costs</td><td>{p.monthly_costs ? `${inr(p.monthly_costs)} a month` : "–"}{p.runway_months != null ? <em> · cash covers {p.runway_months} months</em> : null}</td></tr>
          </tbody>
        </table>
      </section>

      {d.alerts.length > 0 && (
        <section className="rd-sec">
          <h2>Alerts</h2>
          <ul className="rd-alerts">
            {d.alerts.map((a) => (
              <li key={a.id} className={`sev-${a.severity}`}>
                <strong>{money(a.title)}</strong>
                <span>{money(a.detail)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.actions.length > 0 && (
        <section className="rd-sec">
          <h2>Suggested this week</h2>
          <ol className="rd-actions">
            {d.actions.map((a) => <li key={a.title}><strong>{money(a.title)}</strong><span>{money(a.detail)}</span></li>)}
          </ol>
        </section>
      )}

      <div className="rd-cols">
        {d.receivables.length > 0 && (
          <section className="rd-sec">
            <h2>Who owes you</h2>
            <table className="rd-table">
              <thead><tr><th>Customer</th><th>Open</th><th>Usually</th></tr></thead>
              <tbody>
                {d.receivables.map((c) => (
                  <tr key={c.name}><td>{c.name}</td><td>{inr(c.open)}</td>
                    <td>{c.days_late == null ? "–" : c.days_late <= 0 ? "on time" : `${c.days_late} days late`}</td></tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        {d.payables.length > 0 && (
          <section className="rd-sec">
            <h2>What you owe (next 45 days)</h2>
            <table className="rd-table">
              <thead><tr><th>Supplier</th><th>Due</th><th>Amount</th></tr></thead>
              <tbody>
                {d.payables.map((x) => <tr key={x.bill_id}><td>{x.supplier}</td><td>{day(x.due)}</td><td>{inr(x.amount)}</td></tr>)}
                <tr className="rd-strong"><td>Total</td><td /><td>{inr(d.payables_total)}</td></tr>
              </tbody>
            </table>
          </section>
        )}
      </div>

      {d.expenses_30.length > 0 && (
        <section className="rd-sec">
          <h2>Expenses, last 30 days</h2>
          <table className="rd-table rd-two">
            <tbody>{d.expenses_30.map((e) => <tr key={e.category}><td>{e.category}</td><td>{inr(e.amount)}</td></tr>)}</tbody>
          </table>
        </section>
      )}
    </>
  );
}

function fmt(v, unit) {
  if (v == null) return "–";
  if (unit === "days") return `${v} days`;
  if (unit === "%") return `${v}%`;
  return inr(v);
}

function ComparisonBody({ d }) {
  const A = d.a.label, B = d.b.label;
  const maxCat = Math.max(1, ...d.expenses.map((e) => Math.max(e.a, e.b)));
  return (
    <>
      <section className="rd-kpis">
        <Kpi label={`Money in, ${A}`} value={inr(d.a.cash_in)} note={`${B}: ${inr(d.b.cash_in)}`} />
        <Kpi label={`Expenses, ${A}`} value={inr(d.a.expenses)} note={`${B}: ${inr(d.b.expenses)}`} />
        <Kpi label={`Net cash flow, ${A}`} value={signed(d.a.net)} tone={d.a.net < 0 ? "neg" : "pos"} note={`${B}: ${signed(d.b.net)}`} />
        <Kpi label={`Cash at end, ${A}`} value={inr(d.a.closing)} note={`${B}: ${inr(d.b.closing)}`} />
      </section>
      <section className="rd-sec">
        <h2>{A} compared with {B}</h2>
        <table className="rd-table rd-compare">
          <thead><tr><th /><th>{A}</th><th>{B}</th><th>Change</th></tr></thead>
          <tbody>
            {d.rows.map((r) => {
              const better = r.change == null || r.good == null || r.change === 0 ? "" :
                (r.good === "up") === (r.change > 0) ? "pos" : "neg";
              return (
                <tr key={r.key} className={r.key === "net" ? "rd-strong" : ""}>
                  <td>{r.label}</td><td>{fmt(r.a, r.unit)}</td><td>{fmt(r.b, r.unit)}</td>
                  <td className={better}>
                    {r.change == null ? "–" : r.unit === "inr" ? signed(r.change) : `${r.change > 0 ? "+" : ""}${r.change}${r.unit === "%" ? " pts" : " days"}`}
                    {r.pct != null && r.unit === "inr" && <em> ({r.pct > 0 ? "+" : ""}{r.pct}%)</em>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="rd-note">{A}: {day(d.a.from)} to {day(d.a.to)} ({d.a.days} days). {B}: {day(d.b.from)} to {day(d.b.to)} ({d.b.days} days).
          Green means better for your cash, red means worse.</p>
      </section>
      {d.expenses.length > 0 && (
        <section className="rd-sec">
          <h2>Expenses by category</h2>
          <table className="rd-table rd-cats">
            <thead><tr><th>Category</th><th>{A}</th><th>{B}</th><th className="rd-barcol" /></tr></thead>
            <tbody>
              {d.expenses.map((e) => (
                <tr key={e.category}>
                  <td>{e.category}</td><td>{inr(e.a)}</td><td>{inr(e.b)}</td>
                  <td className="rd-barcol">
                    <span className="rd-bar a" style={{ width: `${(e.a / maxCat) * 100}%` }} />
                    <span className="rd-bar b" style={{ width: `${(e.b / maxCat) * 100}%` }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

export default function ReportDoc({ rep }) {
  return (
    <article className="rd">
      <Head rep={rep} />
      {rep.kind === "comparison" ? <ComparisonBody d={rep.data} /> : <SummaryBody d={rep.data} />}
      <footer className="rd-foot">
        Made with Cashwise. Forecasts use each customer's real payment history; they help you decide and are not
        a guarantee or financial advice.
      </footer>
    </article>
  );
}

// Printing: the report is copied into a layer outside the app, and only that layer is printed.
export function PrintLayer({ rep }) {
  if (!rep) return null;
  return createPortal(<div className="print-root"><ReportDoc rep={rep} /></div>, document.body);
}

export function printReport(rep, onPrinted) {
  if (!rep) return;
  const prev = document.title;
  document.title = rep.title;            // becomes the file name when saving as PDF
  onPrinted?.();
  setTimeout(() => {
    window.print();
    document.title = prev;
  }, 50);
}

// The public read-only page at /r/<token>. No sign-in; it shows only this one report.
export function SharedReport({ token }) {
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    document.documentElement.dataset.theme = "light";
    api.publicReport(token).then((r) => { setRep(r); document.title = r.title; }).catch((e) => setErr(e.message));
  }, [token]);
  return (
    <div className="shared">
      <div className="shared-bar">
        <span className="shared-brand"><img src="/logo-light.png" alt="" width="28" height="28" /> Cashwise
          <em>Read-only report</em></span>
        {rep && <button className="btn btn-dark" onClick={() => printReport(rep)}><Icon name="printer" size={16} /> Print or save as PDF</button>}
      </div>
      {err ? (
        <div className="shared-err"><Icon name="link" size={28} /><h1>This link isn't available</h1><p>{err}</p></div>
      ) : !rep ? (
        <div className="boot"><span className="dots" aria-label="Loading"><i /><i /><i /></span></div>
      ) : (
        <div className="shared-paper"><ReportDoc rep={rep} /></div>
      )}
      <PrintLayer rep={rep} />
    </div>
  );
}
