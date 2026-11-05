import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { addDays, when } from "../format.js";
import { Card } from "./Cards.jsx";
import ReportDoc, { PrintLayer, printReport } from "./ReportDoc.jsx";

/*
  Reports: make a report (cash-flow or comparison), then print it, email it to management, or share a
  read-only link. Earlier reports stay in History; schedules make them weekly or monthly by themselves;
  and the audit trail records every financial change and every report action.
*/
const TABS = [
  ["make", "Make a report", "file"],
  ["compare", "Compare periods", "columns"],
  ["history", "Report history", "history"],
  ["scheduled", "Scheduled", "clock"],
  ["shared", "Shared links", "link"],
  ["audit", "Audit trail", "shield"],
];
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// ------------------------------------------------------------------ periods
const iso = (y, m, d) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
function monthOf(isoDate, shift = 0) {
  const [y, m] = isoDate.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1 + shift, 1));
  const Y = t.getUTCFullYear(), M = t.getUTCMonth() + 1;
  const last = new Date(Date.UTC(Y, M, 0)).getUTCDate();
  return [iso(Y, M, 1), iso(Y, M, last)];
}
function presetPeriods(key, asOf) {
  if (key === "last_month") return [monthOf(asOf, -1), monthOf(asOf, -2)];
  if (key === "mtd") {
    const [s] = monthOf(asOf, 0);
    const days = Number(asOf.slice(8, 10));
    const [ps] = monthOf(asOf, -1);
    return [[s, asOf], [ps, addDays(ps, days - 1)]];
  }
  const n = key === "last7" ? 7 : 30;
  const a = [addDays(asOf, -(n - 1)), asOf];
  return [a, [addDays(a[0], -n), addDays(a[0], -1)]];
}
const PRESETS = [["last_month", "Last month vs the month before"], ["mtd", "This month so far vs the same days last month"],
  ["last30", "Last 30 days vs the 30 before"], ["last7", "Last 7 days vs the 7 before"], ["custom", "Choose dates"]];

async function copy(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

// ------------------------------------------------------------------ the viewer: print, email, share
function EmailPanel({ rep, onDone }) {
  const [cfg, setCfg] = useState(null);
  const [to, setTo] = useState("");
  const [mgmt, setMgmt] = useState(true);
  const [note, setNote] = useState("");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => { api.recipients().then((r) => { setCfg(r); setMgmt(r.emails.length > 0); }).catch(() => setCfg({ emails: [] })); }, []);

  const list = () => to.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
  async function go(mode) {
    setBusy(true); setMsg(null);
    try {
      const r = await api.emailReport(rep.report_id, { to: list(), use_management: mgmt, note, mode, link_days: Number(days) || null });
      if (mode === "draft") {
        window.location.href = `mailto:${encodeURIComponent(r.to.join(","))}?subject=${encodeURIComponent(r.subject)}&body=${encodeURIComponent(r.text)}`;
        setMsg({ ok: true, text: "Opened your email app with the report and a read-only link." });
      } else {
        setMsg({ ok: true, text: `Sent to ${r.sent_to.join(", ")}.` });
      }
      onDone?.();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }
  if (!cfg) return <div className="rv-panel"><div className="skeleton" /></div>;
  return (
    <div className="rv-panel">
      <h3><Icon name="mail" size={17} /> Email this report</h3>
      <label className="rv-field">To <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@company.com, another@company.com" /></label>
      <label className="check-row rv-check">
        <input type="checkbox" checked={mgmt} disabled={!cfg.emails.length} onChange={(e) => setMgmt(e.target.checked)} />
        {cfg.emails.length ? <>Send to management: {cfg.emails.join(", ")}</> : <>No management list yet. Add one in the Scheduled tab.</>}
      </label>
      <label className="rv-field">Message (optional)<textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Please look at the 13 Nov payment." /></label>
      <label className="rv-field rv-inline">The report link works for
        <select value={days} onChange={(e) => setDays(e.target.value)}>
          <option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option>
        </select>
      </label>
      <div className="rv-btns">
        {cfg.email_configured && <button className="btn btn-dark" disabled={busy} onClick={() => go("send")}><Icon name="send" size={16} /> {busy ? "Sending…" : "Send email"}</button>}
        <button className={`btn ${cfg.email_configured ? "btn-line" : "btn-dark"}`} disabled={busy} onClick={() => go("draft")}><Icon name="mail" size={16} /> Open in my email app</button>
      </div>
      {!cfg.email_configured && <p className="rv-hint">Sending straight from Cashwise needs email (SMTP) settings on the server. Until then, this opens your own email app with everything filled in.</p>}
      {msg && <p className={msg.ok ? "rv-ok" : "error"} role="status">{msg.text}</p>}
    </div>
  );
}

function SharePanel({ rep, onDone }) {
  const [days, setDays] = useState("30");
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);
  async function make() {
    setBusy(true); setErr("");
    try { const s = await api.shareReport(rep.report_id, days === "never" ? null : Number(days)); setLink(s); onDone?.(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="rv-panel">
      <h3><Icon name="link" size={17} /> Share a read-only link</h3>
      <p className="rv-hint">Anyone with the link can see this report, and only this report. They can't change anything or see the rest of your business. You can turn the link off at any time.</p>
      {!link ? (
        <>
          <label className="rv-field rv-inline">Link works for
            <select value={days} onChange={(e) => setDays(e.target.value)}>
              <option value="1">1 day</option><option value="7">7 days</option><option value="30">30 days</option>
              <option value="90">90 days</option><option value="never">Until I turn it off</option>
            </select>
          </label>
          <div className="rv-btns"><button className="btn btn-dark" disabled={busy} onClick={make}><Icon name="link" size={16} /> {busy ? "Making…" : "Make link"}</button></div>
        </>
      ) : (
        <>
          <div className="rv-link">
            <input readOnly value={link.url} onFocus={(e) => e.target.select()} aria-label="Read-only link" />
            <button className="btn btn-dark" onClick={async () => setCopied(await copy(link.url))}><Icon name="copy" size={16} /> {copied ? "Copied" : "Copy"}</button>
          </div>
          <p className="rv-hint">{link.expires_at ? `Works until ${when(link.expires_at)}.` : "Works until you turn it off."} Manage it in Shared links.</p>
        </>
      )}
      {err && <p className="error">{err}</p>}
    </div>
  );
}

export function ReportViewer({ id, onClose, onChanged, start }) {
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const [panel, setPanel] = useState(start === "print" ? null : start || null);
  useEffect(() => { api.report(id).then(setRep).catch((e) => setErr(e.message)); }, [id]);
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    document.body.classList.add("no-scroll");
    return () => { document.removeEventListener("keydown", esc); document.body.classList.remove("no-scroll"); };
  }, [onClose]);
  useEffect(() => {
    if (start === "print" && rep) { printReport(rep, () => api.printed(rep.report_id).catch(() => {})); setPanel(null); }
  }, [start, rep]);

  // rendered at the top of the page, so nothing in the dashboard can sit on top of it
  return createPortal(
    <div className="rv-back" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="rv" role="dialog" aria-modal="true" aria-label={rep?.title || "Report"}>
        <div className="rv-bar">
          <p className="rv-title">{rep ? rep.title : "Loading report…"}</p>
          <div className="rv-actions">
            <button className="btn btn-dark" disabled={!rep} onClick={() => printReport(rep, () => api.printed(rep.report_id).catch(() => {}))}>
              <Icon name="printer" size={16} /> Print
            </button>
            <button className={`btn btn-line ${panel === "email" ? "is-on" : ""}`} disabled={!rep} onClick={() => setPanel(panel === "email" ? null : "email")}>
              <Icon name="mail" size={16} /> Email
            </button>
            <button className={`btn btn-line ${panel === "share" ? "is-on" : ""}`} disabled={!rep} onClick={() => setPanel(panel === "share" ? null : "share")}>
              <Icon name="link" size={16} /> Share link
            </button>
            <button className="round small" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button>
          </div>
        </div>
        {rep && panel === "email" && <EmailPanel rep={rep} onDone={onChanged} />}
        {rep && panel === "share" && <SharePanel rep={rep} onDone={onChanged} />}
        <div className="rv-paper">
          {err ? <p className="error">{err}</p> : rep ? <ReportDoc rep={rep} /> : <div className="skeleton sk-tall" />}
        </div>
      </div>
      <PrintLayer rep={rep} />
    </div>,
    document.body,
  );
}

// ------------------------------------------------------------------ tabs
function MakeTab({ onMade }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function make() {
    setBusy(true); setErr("");
    try { const r = await api.makeReport({ kind: "summary" }); onMade(r.report_id); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="grid">
      <div className="span-6">
        <Card i={1} className="rp-make">
          <div className="rp-make-text">
            <span className="rp-big-ic"><Icon name="file" size={26} /></span>
            <div>
              <h2>Cash-flow report</h2>
              <p>Today's cash, net cash flow for the next 4 weeks (best, likely and worst), financial position,
                alerts, this week's actions, who owes you and what you owe. Saved as a snapshot, so it never changes after you send it.</p>
              <ul className="rp-does">
                <li><Icon name="printer" size={15} /> Print or save as PDF</li>
                <li><Icon name="mail" size={15} /> Email to management</li>
                <li><Icon name="link" size={15} /> Share a read-only link</li>
              </ul>
            </div>
          </div>
          <button className="btn btn-dark magnet" onClick={make} disabled={busy}>
            <Icon name="sparkle" size={16} /> {busy ? "Making…" : "Make report"}
          </button>
          {err && <p className="error">{err}</p>}
        </Card>
      </div>
    </div>
  );
}

function CompareTab({ biz, onMade }) {
  const [preset, setPreset] = useState("last_month");
  const init = presetPeriods("last_month", biz.as_of);
  const [a, setA] = useState(init[0]);
  const [b, setB] = useState(init[1]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  function pick(k) {
    setPreset(k);
    if (k !== "custom") { const [x, y] = presetPeriods(k, biz.as_of); setA(x); setB(y); }
  }
  async function make() {
    setBusy(true); setErr("");
    try {
      const r = await api.makeReport({ kind: "comparison", a_from: a[0], a_to: a[1], b_from: b[0], b_to: b[1] });
      onMade(r.report_id);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  const Range = ({ label, v, set }) => (
    <div className="rp-range">
      <span>{label}</span>
      <input type="date" value={v[0]} max={biz.as_of} onChange={(e) => { setPreset("custom"); set([e.target.value, v[1]]); }} aria-label={`${label} from`} />
      <em>to</em>
      <input type="date" value={v[1]} max={biz.as_of} onChange={(e) => { setPreset("custom"); set([v[0], e.target.value]); }} aria-label={`${label} to`} />
    </div>
  );
  return (
    <div className="grid">
      <div className="span-6">
        <Card i={1}>
          <div className="card-head"><span className="ic"><Icon name="columns" size={18} /></span>
            <div className="al-gh"><h2>Compare two periods</h2><p>Money in and out, invoicing, how fast customers paid, and expenses by category, side by side.</p></div></div>
          <div className="rp-presets" role="radiogroup" aria-label="Periods">
            {PRESETS.map(([k, label]) => (
              <button key={k} role="radio" aria-checked={preset === k} className={`pill ${preset === k ? "is-on" : ""}`} onClick={() => pick(k)}>{label}</button>
            ))}
          </div>
          <div className="rp-ranges">
            <Range label="This period" v={a} set={setA} />
            <span className="rp-vs">vs</span>
            <Range label="Compared with" v={b} set={setB} />
          </div>
          <div className="rv-btns">
            <button className="btn btn-dark magnet" onClick={make} disabled={busy}><Icon name="columns" size={16} /> {busy ? "Comparing…" : "Make comparison report"}</button>
          </div>
          {err && <p className="error">{err}</p>}
        </Card>
      </div>
    </div>
  );
}

function HistoryTab({ open, refreshKey }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => api.reports().then(setData).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load, refreshKey]);
  async function del(r) {
    if (!window.confirm?.(`Delete "${r.title}"? Its shared links stop working.`)) return;
    try { await api.deleteReport(r.report_id); load(); } catch (e) { setErr(e.message); }
  }
  return (
    <div className="grid"><div className="span-6"><Card i={1}>
      <div className="card-head"><span className="ic"><Icon name="history" size={18} /></span>
        <div className="al-gh"><h2>Report history</h2><p>Every report you or a schedule made. Each is a snapshot of the numbers on the day it was made.</p></div>
        {data && <span className="count">{data.reports.length}</span>}</div>
      {err && <p className="error">{err}</p>}
      {!data ? <div className="skeleton" /> : data.reports.length === 0 ? (
        <p className="empty">No reports yet. Make one in the first tab.</p>
      ) : (
        <ul className="rp-list">
          {data.reports.map((r) => (
            <li key={r.report_id} className="rp-row">
              <span className={`rp-kind ${r.kind}`}><Icon name={r.kind === "comparison" ? "columns" : "file"} size={17} /></span>
              <button className="rp-main" onClick={() => open(r.report_id)}>
                <strong>{r.title}</strong>
                <span>{when(r.created_at)} · {r.created_by.split(" (")[0]}
                  {r.source === "scheduled" && <em className="tag">Scheduled</em>}
                  {r.shares > 0 && <em className="tag">{r.shares} link{r.shares > 1 ? "s" : ""}</em>}</span>
              </button>
              <div className="rp-btns">
                <button className="btn-mini" onClick={() => open(r.report_id)}>Open</button>
                <button className="btn-mini" onClick={() => open(r.report_id, "print")} title="Print"><Icon name="printer" size={14} /></button>
                <button className="btn-mini" onClick={() => open(r.report_id, "email")} title="Email"><Icon name="mail" size={14} /></button>
                <button className="btn-mini" onClick={() => open(r.report_id, "share")} title="Share link"><Icon name="link" size={14} /></button>
                <button className="al-hide" onClick={() => del(r)} title="Delete" aria-label={`Delete ${r.title}`}><Icon name="trash" size={15} /></button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card></div></div>
  );
}

function Recipients({ onChange }) {
  const [v, setV] = useState("");
  const [saved, setSaved] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => { api.recipients().then((r) => { setSaved(r); setV(r.emails.join(", ")); }).catch(() => {}); }, []);
  async function save(e) {
    e.preventDefault(); setMsg(null);
    try {
      const r = await api.setRecipients(v.split(/[,;\s]+/).filter(Boolean));
      setSaved({ ...saved, ...r }); setV(r.emails.join(", ")); setMsg({ ok: true, text: "Saved." }); onChange?.();
    } catch (x) { setMsg({ ok: false, text: x.message }); }
  }
  return (
    <form className="rp-recip" onSubmit={save}>
      <label className="rv-field">Management (who gets reports)
        <input value={v} onChange={(e) => setV(e.target.value)} placeholder="md@company.com, cfo@company.com" />
      </label>
      <button className="btn btn-dark">Save list</button>
      {msg && <p className={msg.ok ? "rv-ok" : "error"}>{msg.text}</p>}
    </form>
  );
}

function ScheduleTab({ onRan }) {
  const [data, setData] = useState(null);
  const [f, setF] = useState({ frequency: "weekly", weekday: 0, day_of_month: 1, hour: 9, kind: "summary", recipients: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => api.schedules().then(setData).catch((e) => setMsg({ ok: false, text: e.message })), []);
  useEffect(() => { load(); }, [load]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const body = (x) => ({ frequency: x.frequency, weekday: Number(x.weekday), day_of_month: Number(x.day_of_month), hour: Number(x.hour),
    kind: x.kind, recipients: Array.isArray(x.recipients) ? x.recipients : String(x.recipients).split(/[,;\s]+/).filter(Boolean),
    active: x.active ?? true });

  async function add(e) {
    e.preventDefault(); setBusy(true); setMsg(null);
    try { await api.addSchedule(body(f)); setF({ ...f, recipients: "" }); setMsg({ ok: true, text: "Schedule added." }); load(); }
    catch (x) { setMsg({ ok: false, text: x.message }); } finally { setBusy(false); }
  }
  async function act(fn, ok) {
    setMsg(null);
    try { const r = await fn(); setMsg({ ok: true, text: ok(r) }); load(); onRan?.(); } catch (x) { setMsg({ ok: false, text: x.message }); }
  }

  return (
    <div className="grid">
      <div className="span-6"><Card i={1}>
        <div className="card-head"><span className="ic"><Icon name="clock" size={18} /></span>
          <div className="al-gh"><h2>Scheduled reports</h2><p>Made automatically every week or month, saved to history, and emailed to management.</p></div></div>
        {data && !data.email_configured && (
          <p className="rp-warn"><Icon name="alert" size={16} /> Email isn't set up on the server yet, so scheduled reports are made and saved to history but not emailed. Add SMTP settings (see DEPLOY.md) to send them.</p>
        )}
        <Recipients onChange={load} />

        <form className="rp-sched-form" onSubmit={add}>
          <label className="rv-field">Report
            <select value={f.kind} onChange={set("kind")}><option value="summary">Cash-flow report</option><option value="comparison">Comparison with the previous period</option></select>
          </label>
          <label className="rv-field">How often
            <select value={f.frequency} onChange={set("frequency")}><option value="weekly">Every week</option><option value="monthly">Every month</option></select>
          </label>
          {f.frequency === "weekly" ? (
            <label className="rv-field">On
              <select value={f.weekday} onChange={set("weekday")}>{WEEKDAYS.map((w, i) => <option key={w} value={i}>{w}</option>)}</select>
            </label>
          ) : (
            <label className="rv-field">On day
              <select value={f.day_of_month} onChange={set("day_of_month")}>{Array.from({ length: 28 }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select>
            </label>
          )}
          <label className="rv-field">At
            <select value={f.hour} onChange={set("hour")}>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}</select>
          </label>
          <label className="rv-field rp-wide">Send to (leave empty for the management list)
            <input value={f.recipients} onChange={set("recipients")} placeholder="Management list" />
          </label>
          <button className="btn btn-dark" disabled={busy}><Icon name="plus" size={16} /> Add schedule</button>
        </form>
        {msg && <p className={msg.ok ? "rv-ok" : "error"} role="status">{msg.text}</p>}

        {!data ? <div className="skeleton" /> : data.schedules.length === 0 ? (
          <p className="empty">No schedules yet.</p>
        ) : (
          <ul className="rp-list">
            {data.schedules.map((s) => (
              <li key={s.schedule_id} className={`rp-row ${s.active ? "" : "is-paused"}`}>
                <span className="rp-kind"><Icon name="clock" size={17} /></span>
                <div className="rp-main">
                  <strong>{s.description}{!s.active && <em className="tag">Paused</em>}</strong>
                  <span>To {s.recipients.length ? s.recipients.join(", ") : `management${data.management.length ? ` (${data.management.join(", ")})` : " (no list yet)"}`}</span>
                  <span>{s.active ? `Next: ${when(s.next_run)}` : "Not running"}{s.last_run ? ` · Last: ${when(s.last_run)}, ${s.last_status}` : ""}</span>
                </div>
                <div className="rp-btns">
                  <button className="btn-mini" onClick={() => act(() => api.runSchedule(s.schedule_id), (r) => `${r.status}. It's in Report history.`)}>Run now</button>
                  <button className="btn-mini" title={s.active ? "Pause" : "Resume"} onClick={() => act(() => api.editSchedule(s.schedule_id, body({ ...s, active: !s.active })), () => (s.active ? "Paused." : "Resumed."))}>
                    <Icon name={s.active ? "pause" : "play"} size={14} />
                  </button>
                  <button className="al-hide" title="Delete" aria-label="Delete schedule" onClick={() => act(() => api.deleteSchedule(s.schedule_id), () => "Schedule deleted.")}><Icon name="trash" size={15} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {data && <p className="rp-foot">Times are {data.timezone}. If the server is asleep at that time, the report is made as soon as it wakes.</p>}
      </Card></div>
    </div>
  );
}

function SharedTab({ refreshKey }) {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => api.shares().then(setData).catch((e) => setMsg({ ok: false, text: e.message })), []);
  useEffect(() => { load(); }, [load, refreshKey]);
  async function off(s) {
    try { await api.revokeShare(s.token); setMsg({ ok: true, text: "Link turned off. It no longer opens." }); load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  return (
    <div className="grid"><div className="span-6"><Card i={1}>
      <div className="card-head"><span className="ic"><Icon name="link" size={18} /></span>
        <div className="al-gh"><h2>Shared links</h2><p>Read-only links to single reports. Turn one off and it stops working straight away.</p></div></div>
      {msg && <p className={msg.ok ? "rv-ok" : "error"} role="status">{msg.text}</p>}
      {!data ? <div className="skeleton" /> : data.shares.length === 0 ? (
        <p className="empty">No links yet. Open a report and choose Share link.</p>
      ) : (
        <ul className="rp-list">
          {data.shares.map((s) => (
            <li key={s.token} className={`rp-row ${s.active ? "" : "is-paused"}`}>
              <span className={`rp-kind ${s.active ? "" : "off"}`}><Icon name="link" size={17} /></span>
              <div className="rp-main">
                <strong>{s.title} <em className={`tag ${s.active ? "ok" : ""}`}>{s.active ? "Active" : s.revoked ? "Turned off" : "Expired"}</em></strong>
                <span>Made {when(s.created_at)} · {s.expires_at ? `${s.expired ? "expired" : "expires"} ${when(s.expires_at)}` : "no expiry"}</span>
                <span>{s.views} view{s.views === 1 ? "" : "s"}{s.last_viewed_at ? `, last ${when(s.last_viewed_at)}` : ""}</span>
              </div>
              {s.active && (
                <div className="rp-btns">
                  <button className="btn-mini" onClick={async () => setMsg({ ok: true, text: (await copy(s.url)) ? "Link copied." : s.url })}><Icon name="copy" size={14} /> Copy</button>
                  <a className="btn-mini" href={s.url} target="_blank" rel="noreferrer">Open</a>
                  <button className="btn-mini danger" onClick={() => off(s)}>Turn off</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card></div></div>
  );
}

const AUDIT_CATS = [["", "Everything"], ["money", "Money"], ["data", "Data"], ["report", "Reports"], ["sharing", "Sharing"], ["settings", "Settings"]];
const AUDIT_ICON = { money: "wallet", data: "upload", report: "file", sharing: "link", settings: "settings" };

function AuditTab({ refreshKey }) {
  const [cat, setCat] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { setData(null); api.audit(cat).then(setData).catch((e) => setErr(e.message)); }, [cat, refreshKey]);
  return (
    <div className="grid"><div className="span-6"><Card i={1}>
      <div className="card-head"><span className="ic"><Icon name="shield" size={18} /></span>
        <div className="al-gh"><h2>Audit trail</h2><p>Every important financial change and every report action: who did it, and when. Entries can't be edited.</p></div></div>
      <div className="al-filters">
        {AUDIT_CATS.map(([k, label]) => (
          <button key={k || "all"} role="tab" aria-selected={cat === k} className="pill" onClick={() => setCat(k)}>{label}</button>
        ))}
      </div>
      {err && <p className="error">{err}</p>}
      {!data ? <div className="skeleton" /> : data.entries.length === 0 ? (
        <p className="empty">Nothing recorded yet.</p>
      ) : (
        <ol className="au-list">
          {data.entries.map((e) => (
            <li key={e.entry_id} className={`au-row c-${e.category}`}>
              <span className="au-ic"><Icon name={AUDIT_ICON[e.category] || "help"} size={15} /></span>
              <div className="au-text">
                <p className="au-what"><strong>{e.action.replace(".", " · ").replace(/_/g, " ")}</strong> <span>{e.detail}</span></p>
                <p className="au-who">{when(e.at)} · {e.actor}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card></div></div>
  );
}

// ------------------------------------------------------------------ the page
export default function ReportsPage({ biz }) {
  const [tab, setTab] = useState("make");
  const [viewing, setViewing] = useState(null);     // { id, start }
  const [bump, setBump] = useState(0);
  const refresh = () => setBump((n) => n + 1);
  const open = (id, start) => setViewing({ id, start });

  return (
    <div className="reports">
      <div className="rp-tabs" role="tablist" aria-label="Reports">
        {TABS.map(([k, label, icon]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`rp-tab ${tab === k ? "is-on" : ""}`} onClick={() => setTab(k)}>
            <Icon name={icon} size={16} /> {label}
          </button>
        ))}
      </div>
      {tab === "make" && <MakeTab onMade={(id) => { refresh(); open(id); }} />}
      {tab === "compare" && <CompareTab biz={biz} onMade={(id) => { refresh(); open(id); }} />}
      {tab === "history" && <HistoryTab open={open} refreshKey={bump} />}
      {tab === "scheduled" && <ScheduleTab onRan={refresh} />}
      {tab === "shared" && <SharedTab refreshKey={bump} />}
      {tab === "audit" && <AuditTab refreshKey={bump} />}
      {viewing && <ReportViewer id={viewing.id} start={viewing.start} onChanged={refresh}
        onClose={() => { setViewing(null); refresh(); }} />}
    </div>
  );
}
