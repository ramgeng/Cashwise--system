import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import useCountUp from "../useCountUp.js";
import { day, inr, leftOrShort, longDay, money } from "../format.js";
import { MemorySwitch } from "./Shell.jsx";

// Animated number that rolls to its new value.
export function Num({ value, format = inr, className = "" }) {
  const v = useCountUp(value ?? 0);
  return <span className={className}>{format(Math.round(v))}</span>;
}

export function Card({ i = 0, className = "", children, ...rest }) {
  return (
    <section className={`card ${className}`} style={{ "--i": i }} {...rest}>
      {children}
    </section>
  );
}

// ------------------------------------------------------------- cash today
// Type in what the bank actually shows. The backend adds one adjustment so the books agree with the bank.
function BalanceEditor({ biz, onDone, onCancel }) {
  const [v, setV] = useState(String(biz.cash));
  const [on, setOn] = useState(biz.as_of);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const input = useRef(null);
  useEffect(() => { input.current?.focus(); input.current?.select(); }, []);

  async function save(e) {
    e.preventDefault();
    const n = Math.round(Number(String(v).replace(/[₹,\s]/g, "")));
    if (!Number.isFinite(n)) { setErr("Enter the amount in rupees, like 1200325."); return; }
    setBusy(true); setErr("");
    try { await api.updateBusiness({ bank_balance: n, bank_balance_date: on }); onDone(); }
    catch (x) { setErr(x.message); setBusy(false); }
  }
  return (
    <form className="bal-edit" onSubmit={save} onKeyDown={(e) => e.key === "Escape" && onCancel()}>
      <label className="bal-edit-amt">
        <span>₹</span>
        <input ref={input} inputMode="numeric" value={v} onChange={(e) => setV(e.target.value)} aria-label="Bank balance in rupees" />
      </label>
      <label className="bal-edit-date">Balance at the end of
        <input type="date" value={on} max={biz.as_of} onChange={(e) => setOn(e.target.value)} />
      </label>
      <div className="bal-edit-btns">
        <button className="btn btn-dark" disabled={busy}>{busy ? "Saving…" : "Save balance"}</button>
        <button type="button" className="btn btn-line" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
      <p className="bal-edit-note">Copy it from your bank app or statement. Records dated after this day will still move it.</p>
      {err && <p className="error">{err}</p>}
    </form>
  );
}

export function BalanceCard({ biz, fc, onAsk, onRecord, onOpenForecast, onChanged, i }) {
  const [hidden, setHidden] = useState(false);
  const [editing, setEditing] = useState(false);
  const set = biz.bank_balance_set;
  async function undo() {
    try { await api.updateBusiness({ clear_bank_balance: true }); onChanged?.(); } catch { /* shown on next load */ }
  }
  const owed = fc.invoice_outlook.reduce((s, o) => s + o.outstanding, 0);
  return (
    <Card i={i} className="balance tilt">
      <div className="bal-top">
        <span className="chip-soft"><Icon name="wallet" size={16} /> Bank balance</span>
        <div className="asof">
          <span>As of</span>
          <strong>{longDay(biz.as_of)}</strong>
        </div>
      </div>
      <p className="label">Cash in bank today</p>
      {editing ? (
        <BalanceEditor biz={biz} onCancel={() => setEditing(false)} onDone={() => { setEditing(false); onChanged?.(); }} />
      ) : (
        <>
          <div className="bal-row">
            <p className="big">{hidden ? "₹ •• •• •••" : <Num value={biz.cash} format={(n) => `₹${n.toLocaleString("en-IN")}`} />}</p>
            <button className="eye" onClick={() => setHidden(!hidden)} aria-label={hidden ? "Show balance" : "Hide balance"}>
              <Icon name={hidden ? "eyeOff" : "eye"} size={18} />
            </button>
            <button className="eye" onClick={() => setEditing(true)} aria-label="Update bank balance" title="Update bank balance">
              <Icon name="pencil" size={17} />
            </button>
          </div>
          <p className="bal-src">
            {set ? <>Matched to your bank on {day(set.date)} · <button className="link" onClick={undo}>Undo</button></>
              : <>Worked out from your records · <button className="link" onClick={() => setEditing(true)}>Update from bank</button></>}
          </p>
        </>
      )}
      <div className="bal-stats">
        <span>Owed to you <strong>{inr(owed)}</strong></span>
        <span>Bills next 4 weeks <strong>{inr(fc.events.filter((e) => e.kind === "bill").reduce((s, e) => s - e.amount, 0))}</strong></span>
      </div>
      <div className="bal-actions">
        <button className="btn btn-dark magnet" onClick={onAsk}><Icon name="sparkle" size={16} /> Ask the agent</button>
        <button className="btn btn-line magnet" onClick={onRecord}><Icon name="check" size={16} /> Record outcome</button>
      </div>
      <button className="go magnet" onClick={onOpenForecast} aria-label="Open the full forecast">
        <Icon name="arrowUpRight" size={26} stroke={2.2} />
      </button>
    </Card>
  );
}

// ------------------------------------------------------------- net cash flow
// Money in minus money out over the next 4 weeks, in three scenarios built from real payment habits.
const signed = (n) => inr(n, { signed: true });

export function ForecastHero({ fc, memory, setMemory, scenario, busy, onOpenGraph, i }) {
  const [pick, setPick] = useState("likely");
  const { key_bill, target_date, summary, flow } = fc;
  const f = flow ? (memory ? flow[pick] : flow.naive) : null;
  const label = memory ? { best: "best case", likely: "likely", worst: "worst case" }[pick] : "if everyone pays on time";
  const s = memory ? summary[pick] : summary.naive;
  const total = f ? Math.max(f.in, f.out, 1) : 1;

  if (!f) return null;
  return (
    <Card i={i} className="hero-card tilt">
      <div className="hero-top">
        <MemorySwitch memory={memory} setMemory={setMemory} />
        <span className="hero-date">Next 4 weeks · to {day(fc.horizon_end)}</span>
      </div>
      <p className="label">Net cash flow</p>
      <div className="hero-row">
        <Num value={f.net} format={signed} className={`hero-big ${f.net < 0 ? "neg" : "pos"}`} />
        <span className="hero-chip">{label}</span>
      </div>

      <div className="flow-bars" aria-label="Money in and out">
        <div className="flow-row">
          <span className="flow-k"><Icon name="arrowDownLeft" size={14} stroke={2.4} /> Coming in</span>
          <span className="flow-track"><i className="in" style={{ width: `${(f.in / total) * 100}%` }} /></span>
          <strong>{inr(f.in)}</strong>
        </div>
        <div className="flow-row">
          <span className="flow-k"><Icon name="arrowUpRight" size={14} stroke={2.4} /> Going out</span>
          <span className="flow-track"><i className="out" style={{ width: `${(f.out / total) * 100}%` }} /></span>
          <strong>{inr(f.out)}</strong>
        </div>
        <p className="flow-cash">Cash <strong>{inr(f.opening)}</strong> today → <strong className={f.closing < 0 ? "neg" : ""}>{inr(f.closing)}</strong> on {day(fc.horizon_end)}</p>
      </div>

      {memory ? (
        <>
          <div className="scen" role="radiogroup" aria-label="Scenario">
            {["best", "likely", "worst"].map((k) => (
              <button key={k} role="radio" aria-checked={pick === k} className={`scen-box ${pick === k ? "is-on" : ""}`}
                onClick={() => setPick(k)}>
                <span>{k === "likely" ? "Likely" : k === "best" ? "Best case" : "Worst case"}</span>
                <strong className={flow[k].net < 0 ? "neg" : ""}>{signed(flow[k].net)}</strong>
              </button>
            ))}
          </div>
          {scenario ? (
            <div className={`hero-whatif ${busy ? "is-busy" : ""}`}>
              <span>With the actions you ticked: likely <strong className={scenario.likely.on_target < 0 ? "neg" : ""}>{leftOrShort(scenario.likely.on_target)}</strong> on {day(target_date)}</span>
              <button className="link" onClick={onOpenGraph}>See on graph</button>
            </div>
          ) : key_bill ? (
            <p className="hero-foot">
              Tightest day: after paying {key_bill.supplier.split(" ")[0]} {inr(key_bill.amount)} on {day(target_date)}, {" "}
              <strong className={s.on_target < 0 ? "neg" : "pos"}>{leftOrShort(s.on_target)}</strong>.
              {" "}A due-date dashboard would say <s>{leftOrShort(summary.naive.on_target)}</s>
            </p>
          ) : null}
        </>
      ) : (
        <p className="hero-foot">This assumes every customer pays on the due date. Switch memory on to see how they really pay.</p>
      )}
    </Card>
  );
}

// ------------------------------------------------------------- overall financial position
export function PositionCard({ data, i }) {
  if (!data) return <div className="skeleton sk-pos" />;
  const d = data;
  const cover = d.cover;
  const tone = cover == null ? "" : cover >= 1.5 ? "good" : cover >= 1 ? "ok" : "bad";
  return (
    <Card i={i} className="position-card">
      <div className="card-head">
        <span className="ic"><Icon name="scale" size={18} /></span>
        <h2>Financial position</h2>
        <span className="pos-asof">as of {day(d.as_of)}</span>
      </div>

      <div className="pos-eq">
        <div className="pos-tile">
          <span>Cash in bank</span>
          <Num value={d.cash} className="pos-v" />
        </div>
        <span className="pos-op" aria-hidden="true">+</span>
        <div className="pos-tile">
          <span>Owed to you</span>
          <Num value={d.receivable} className="pos-v" />
          {d.receivable_overdue > 0 && <em className="warn">{inr(d.receivable_overdue)} overdue</em>}
        </div>
        <span className="pos-op" aria-hidden="true">−</span>
        <div className="pos-tile">
          <span>You owe</span>
          <Num value={d.payable} className="pos-v" />
          <em>{inr(d.payable_30)} due in 30 days</em>
        </div>
        <span className="pos-op" aria-hidden="true">=</span>
        <div className={`pos-tile pos-net ${d.net_position < 0 ? "is-neg" : ""}`}>
          <span>Net position</span>
          <Num value={d.net_position} format={(n) => inr(n)} className="pos-v" />
          <em>{d.net_position >= 0 ? "You own more than you owe" : "You owe more than you have and are owed"}</em>
        </div>
      </div>

      <div className="pos-stats">
        <div className={`pos-stat ${tone}`}>
          <span>Cover</span>
          <strong>{cover == null ? "–" : `${cover.toFixed(2)}×`}</strong>
          <em>{cover == null ? "No bills owed" : `₹${cover.toFixed(2)} of cash and receivables for every ₹1 you owe`}</em>
        </div>
        <div className="pos-stat">
          <span>Last 30 days</span>
          <strong className={d.last_30.net < 0 ? "neg" : "pos"}>{inr(d.last_30.net, { signed: true })}</strong>
          <em>{inr(d.last_30.in)} in · {inr(d.last_30.out)} out</em>
        </div>
        <div className="pos-stat">
          <span>Running costs</span>
          <strong>{d.monthly_costs ? `${inr(d.monthly_costs)}/mo` : "–"}</strong>
          <em>{d.runway_months != null ? `Cash alone covers about ${d.runway_months} months` : "Upload expenses to see this"}</em>
        </div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------- this week
export function ActionsCard({ data, memory, previewing, onPreview, i }) {
  const [hidden, setHidden] = useState([]);
  const list = (data?.actions || []).filter((a) => !hidden.includes(a.title));
  return (
    <Card i={i} className="actions-card">
      <div className="card-head">
        <span className="ic"><Icon name="alert" size={18} /></span>
        <h2>This week</h2>
        {memory && list.length > 0 && <span className="count">{list.length}</span>}
      </div>
      {!memory ? (
        <p className="empty">With every invoice assumed on time, nothing needs doing. Switch memory on to see the risks.</p>
      ) : !data ? (
        <div className="skeleton" />
      ) : list.length === 0 ? (
        <p className="empty">Nothing urgent before the next big bill.</p>
      ) : (
        <ul className="act-list">
          {list.map((a) => {
            const on = previewing.some((c) => JSON.stringify(c) === JSON.stringify(a.change));
            return (
              <li key={a.title} className={`act-row ${on ? "is-on" : ""}`}>
                <span className={`act-ic ${a.kind}`}><Icon name={a.kind === "negotiate" ? "handshake" : "phone"} size={18} /></span>
                <div className="act-text">
                  <p className="act-title">{money(a.title)}</p>
                  <p className="act-detail">{money(a.detail)}</p>
                </div>
                <div className="act-btns">
                  <button className={`yes ${on ? "is-on" : ""}`} onClick={() => onPreview(a.change)}
                    aria-pressed={on} title={on ? "Remove from the forecast" : "Add to the forecast to see its effect"}>
                    <Icon name="check" size={16} stroke={2.6} />
                  </button>
                  <button className="no" onClick={() => setHidden([...hidden, a.title])} title="Dismiss">
                    <Icon name="x" size={16} stroke={2.4} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------- who owes you (donut)
function Donut({ parts, size = 168, stroke = 16 }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--track)" strokeWidth={stroke} />
      {parts.map((p, idx) => {
        const len = (p.value / total) * c;
        const el = (
          <circle key={idx} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={p.color} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={`${Math.max(len - 6, 0)} ${c}`} strokeDashoffset={-offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`} className="donut-seg" style={{ "--len": len, "--c": c }} />
        );
        offset += len;
        return el;
      })}
    </svg>
  );
}

export function ReceivablesCard({ fc, customers, i, onOpen }) {
  const key = `chance_paid_in_full_by_${fc.target_date}`;
  let risk = 0, safe = 0, later = 0, riskCount = 0;
  for (const o of fc.invoice_outlook) {
    if (o.due > fc.target_date) later += o.outstanding;
    else if ((o[key] ?? 100) < 70) { risk += o.outstanding; riskCount += 1; }
    else safe += o.outstanding;
  }
  const total = risk + safe + later;
  const top = (customers || []).filter((c) => c.open_total).slice(0, 4);
  return (
    <Card i={i} className="recv">
      <div className="card-head">
        <span className="ic"><Icon name="users" size={18} /></span>
        <h2>Who owes you</h2>
        <button className="chip-btn" onClick={onOpen}>All</button>
      </div>
      <div className="donut-wrap">
        <Donut parts={[{ value: safe, color: "var(--accent-strong)" }, { value: risk, color: "var(--neg)" },
          { value: later, color: "var(--muted)" }]} />
        <div className="donut-center">
          <Num value={total} className="donut-big" />
          <span className="neg-text">{inr(risk)} at risk</span>
        </div>
      </div>
      <p className="note-pill"><Icon name="alert" size={15} /> {riskCount} invoices may miss {day(fc.target_date)}</p>
      <ul className="legend-grid">
        {top.map((c) => (
          <li key={c.customer_id}>
            <i className={c.median_days_late > 7 ? "d-neg" : "d-ok"} />
            <span>{c.name.split(" ")[0]}</span>
            <strong>{inr(c.open_total)}</strong>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ------------------------------------------------------------- what you owe (bars)
export function PayablesCard({ bills, fc, i, onOpen }) {
  if (!bills) return <Card i={i}><div className="skeleton" /></Card>;
  const bySup = {};
  for (const b of bills.bills) bySup[b.supplier] = (bySup[b.supplier] || 0) + b.amount;
  const rows = Object.entries(bySup).sort((a, b) => b[1] - a[1]);
  const total = rows.reduce((s, r) => s + r[1], 0);
  const soon = bills.bills.filter((b) => b.due <= fc.target_date).reduce((s, b) => s + b.amount, 0);
  return (
    <Card i={i} className="pay">
      <div className="card-head">
        <span className="ic"><Icon name="receipt" size={18} /></span>
        <h2>What you owe</h2>
        <button className="chip-btn" onClick={onOpen}>All</button>
      </div>
      <p className="mid"><Num value={soon} /></p>
      <p className="sub">due by {day(fc.target_date)}, of {inr(total)} in the next 6 weeks</p>
      <ul className="bars">
        {rows.slice(0, 4).map(([name, amt], idx) => {
          const pct = Math.round((amt / total) * 100);
          return (
            <li key={name}>
              <div className="bar-head"><span>{name.replace(" Pvt Ltd", "")}</span><strong>{inr(amt)}</strong></div>
              <div className="bar"><span style={{ "--w": `${pct}%`, "--d": `${idx * 90}ms` }}>{idx === 0 && <em>{pct}%</em>}</span></div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
