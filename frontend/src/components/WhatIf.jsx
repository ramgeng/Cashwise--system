import { day, inr, leftOrShort, addDays } from "../format.js";

// Build the list of what-if changes the API understands from the controls.
export function buildChanges(w, keyBill) {
  const ch = [];
  if (w.delay > 0) ch.push({ type: "delay_customer", customer_id: w.customer, days: w.delay });
  if (keyBill && w.payNow !== null && w.payNow < keyBill.amount) {
    ch.push({ type: "split_bill", bill_id: keyBill.bill_id, amount: w.payNow, date: keyBill.due,
              rest_date: addDays(keyBill.due, 14) });
  }
  if (w.collections !== 0) ch.push({ type: "collections_change", pct: w.collections });
  return [...ch, ...w.pinned];
}

export default function WhatIf({ w, setW, customers, keyBill, scenario, base, busy, error }) {
  const active = buildChanges(w, keyBill).length > 0;
  const payNow = w.payNow ?? keyBill?.amount ?? 0;
  const custName = (id) => customers?.find((c) => c.customer_id === id)?.name || id;

  return (
    <section className="whatif" aria-label="Try a what-if">
      <div className="wi-head">
        <h2>Try a what-if</h2>
        {active && (
          <button className="link" onClick={() => setW({ ...w, delay: 0, payNow: null, collections: 0, pinned: [] })}>
            Reset
          </button>
        )}
      </div>

      <div className="wi-controls">
        <div className="ctl">
          <label htmlFor="wi-cust">A customer pays later</label>
          <div className="ctl-row">
            <select id="wi-cust" value={w.customer} onChange={(e) => setW({ ...w, customer: e.target.value })}>
              {(customers || []).map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
            </select>
            <output>{w.delay ? `+${w.delay} days` : "as usual"}</output>
          </div>
          <input type="range" min="0" max="30" step="1" value={w.delay} aria-label="Extra days late"
            onChange={(e) => setW({ ...w, delay: +e.target.value })} />
        </div>

        {keyBill && (
          <div className="ctl">
            <label htmlFor="wi-pay">Pay {keyBill.supplier.split(" ")[0]} on {day(keyBill.due)}</label>
            <div className="ctl-row">
              <span className="ctl-note">rest on {day(addDays(keyBill.due, 14))}</span>
              <output>{payNow >= keyBill.amount ? `all ${inr(keyBill.amount)}` : inr(payNow)}</output>
            </div>
            <input id="wi-pay" type="range" min="0" max={keyBill.amount} step="50000" value={payNow}
              onChange={(e) => setW({ ...w, payNow: +e.target.value })} />
          </div>
        )}

        <div className="ctl">
          <label htmlFor="wi-col">All collections</label>
          <div className="ctl-row">
            <span className="ctl-note">e.g. a slow festival month</span>
            <output>{w.collections > 0 ? `+${w.collections}%` : `${w.collections}%`}</output>
          </div>
          <input id="wi-col" type="range" min="-50" max="20" step="5" value={w.collections}
            onChange={(e) => setW({ ...w, collections: +e.target.value })} />
        </div>
      </div>

      {w.pinned.length > 0 && (
        <ul className="pins">
          {w.pinned.map((p, i) => (
            <li key={i}>
              {custName(p.customer_id)} pays on {day(p.date)}
              <button aria-label="Remove" onClick={() => setW({ ...w, pinned: w.pinned.filter((_, j) => j !== i) })}>×</button>
            </li>
          ))}
        </ul>
      )}

      <p className={`wi-result ${busy ? "is-busy" : ""}`} aria-live="polite">
        {error ? <span className="error">{error}</span>
          : !active ? "Move a slider or pick an action from This week to see its effect on the chart."
          : scenario ? (
            <>
              On {day(scenario.target_date)} you would likely have{" "}
              <strong className={scenario.likely.on_target < 0 ? "neg" : "pos"}>{leftOrShort(scenario.likely.on_target)}</strong>
              {" "}instead of {leftOrShort(base)}. Lowest point {inr(scenario.likely.lowest)} on {day(scenario.likely.lowest_date)}.
            </>
          ) : "Working it out…"}
      </p>
    </section>
  );
}
