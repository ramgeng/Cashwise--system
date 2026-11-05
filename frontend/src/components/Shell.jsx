import { useEffect, useRef, useState } from "react";
import Icon from "../icons.jsx";
import { inr, leftOrShort, longDay, money } from "../format.js";

export const VIEWS = [
  ["overview", "Overview", "home"],
  ["alerts", "Smart alerts", "shield"],
  ["forecast", "Cash forecast", "chart"],
  ["customers", "Who owes you", "users"],
  ["bills", "What you owe", "receipt"],
  ["memory", "Memory", "brain"],
  ["data", "Your data", "upload"],
  ["reports", "Reports", "file"],
];

// The Cashwise mark. "on" is the background it sits on: "dark", "light", or "auto" to follow the theme.
const PILLS = ["overview", "forecast", "customers", "bills"];

export function Logo({ on = "auto", size = 44 }) {
  const img = (v) => <img className={`logo-img logo-${v}`} src={`/logo-${v}.png`} alt="" width={size} height={size} draggable="false" />;
  if (on === "dark") return <span className="logo-mark">{img("dark")}</span>;
  if (on === "light") return <span className="logo-mark">{img("light")}</span>;
  return <span className="logo-mark is-auto">{img("light")}{img("dark")}</span>;
}

export function Sidebar({ view, setView, alerts, smartAlerts = 0, user, onSignOut }) {
  return (
    <nav className="sidebar" aria-label="Main">
      <div className="logo">
        <Logo on="dark" />
        <div>
          <p className="logo-name">Cashwise</p>
          <p className="logo-tag">Your AI cash-flow companion</p>
        </div>
      </div>
      <ul className="nav">
        {VIEWS.map(([k, label, icon]) => (
          <li key={k}>
            <button className={`nav-item ${view === k ? "is-active" : ""}`} onClick={() => setView(k)}
              aria-current={view === k ? "page" : undefined}>
              <Icon name={icon} />
              <span>{label}</span>
              {k === "overview" && alerts > 0 && <span className="badge">{alerts}</span>}
              {k === "alerts" && smartAlerts > 0 && <span className="badge">{smartAlerts}</span>}
            </button>
          </li>
        ))}
      </ul>
      <div className="side-foot">
        <p className="side-note">
          Forecasts use each customer's real payment history. Advice is for your decision, not a guarantee.
        </p>
        {user && (
          <div className="me">
            <span className="me-text"><strong>{user.name}</strong><span>{user.email}</span></span>
            <button className="nav-item signout" onClick={onSignOut} aria-label="Sign out" title="Sign out">
              <Icon name="logout" /><span>Sign out</span>
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}

export function ThemeSwitch({ dark, setDark }) {
  return (
    <button className="theme-switch magnet" onClick={() => setDark(!dark)} role="switch" aria-checked={dark}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
      <span className="ts-track">
        <span className="ts-knob"><Icon name={dark ? "moon" : "sun"} size={14} stroke={2.2} /></span>
      </span>
    </button>
  );
}

export function MemorySwitch({ memory, setMemory, compact = false }) {
  return (
    <button className={`mem-switch ${memory ? "is-on" : ""} ${compact ? "compact" : ""}`}
      onClick={() => setMemory(!memory)} role="switch" aria-checked={memory}>
      <span>Memory {memory ? "on" : "off"}</span>
      <span className="ms-knob"><Icon name={memory ? "check" : "x"} size={14} stroke={2.6} /></span>
    </button>
  );
}

function BusinessMenu({ biz, businesses, onSwitch, onAdd, onSignOut }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="biz-menu" ref={ref}>
      <button className="biz-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="menu">
        {biz?.name || "Loading"} <Icon name="chevron" size={14} stroke={2.4} />
      </button>
      {open && (
        <div className="menu" role="menu">
          <p className="menu-label">Your businesses</p>
          {businesses.map((b) => (
            <button key={b.id} role="menuitemradio" aria-checked={b.id === biz?.id} className="menu-item"
              onClick={() => { setOpen(false); onSwitch(b.id); }}>
              <span><strong>{b.name}</strong>{b.city && <em>{b.city}</em>}</span>
              {b.id === biz?.id && <Icon name="check" size={16} stroke={2.6} />}
            </button>
          ))}
          <button role="menuitem" className="menu-item add" onClick={() => { setOpen(false); onAdd(); }}>
            <Icon name="plus" size={16} stroke={2.4} /> Add a business
          </button>
          <button role="menuitem" className="menu-item add" onClick={() => { setOpen(false); onSignOut(); }}>
            <Icon name="logout" size={16} stroke={2.2} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ notifications
// Built from what the dashboard already knows: the next big bill and this week's actions.
// What you've opened is remembered per business in this browser, so the badge clears once seen.
const seenKey = (id) => `cashwise-seen-${id}`;
const readSeen = (id) => { try { return JSON.parse(localStorage.getItem(seenKey(id)) || "[]"); } catch { return []; } };
const writeSeen = (id, ids) => { try { localStorage.setItem(seenKey(id), JSON.stringify(ids)); } catch { /* ignore */ } };

function buildNotes(fc, actions, memory, smart) {
  const notes = [];
  const c = smart?.counts;
  if (c && (c.critical || c.warning)) {
    notes.push({ id: `alerts:${c.critical}:${c.warning}:${smart.as_of}`, kind: "alerts", icon: "shield",
      title: `${c.critical ? `${c.critical} urgent` : ""}${c.critical && c.warning ? ", " : ""}${c.warning ? `${c.warning} to watch` : ""} in Smart alerts`,
      detail: "Low cash, cash-flow risks and unusual expenses.", bad: c.critical > 0, view: "alerts" });
  }
  if (fc?.key_bill) {
    const likely = fc.summary?.likely?.on_target;
    notes.push({
      id: `bill:${fc.key_bill.supplier}:${fc.target_date}`, kind: "bill", icon: "receipt",
      title: `${fc.key_bill.supplier} ${inr(fc.key_bill.amount)} due ${longDay(fc.target_date)}`,
      detail: likely == null ? "Your next big bill." : memory
        ? `Likely ${leftOrShort(likely)} after paying it.`
        : "Switch memory on to see if you can cover it.",
      bad: memory && likely < 0, view: "bills",
    });
  }
  if (memory) {
    for (const a of actions?.actions || []) {
      notes.push({ id: `act:${a.title}`, kind: a.kind, icon: a.kind === "negotiate" ? "handshake" : "phone",
        title: money(a.title), detail: money(a.detail), change: a.change });
    }
  }
  return notes;
}

function Notifications({ biz, fc, actions, memory, previewing, onPreview, setView, smart }) {
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState([]);
  const ref = useRef(null);
  useEffect(() => { if (biz?.id) setSeen(readSeen(biz.id)); }, [biz?.id]);
  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const notes = buildNotes(fc, actions, memory, smart);
  const unread = notes.filter((n) => !seen.includes(n.id));
  const markAll = () => { const ids = [...new Set([...seen, ...notes.map((n) => n.id)])]; setSeen(ids); biz?.id && writeSeen(biz.id, ids); };
  const markOne = (id) => { if (seen.includes(id)) return; const ids = [...seen, id]; setSeen(ids); biz?.id && writeSeen(biz.id, ids); };
  const isOn = (c) => c && previewing.some((p) => JSON.stringify(p) === JSON.stringify(c));

  return (
    <div className="notif" ref={ref}>
      <button className={`round magnet ${open ? "is-open" : ""}`} onClick={() => setOpen(!open)} aria-expanded={open}
        aria-haspopup="dialog" aria-label={unread.length ? `${unread.length} new notifications` : "Notifications"}>
        <Icon name="bell" />
        {unread.length > 0 && <span className="dot-badge">{unread.length}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-head">
            <p>Notifications</p>
            {unread.length > 0 && <button className="link" onClick={markAll}>Mark all read</button>}
          </div>
          {notes.length === 0 ? (
            <p className="notif-empty"><Icon name="check" size={18} stroke={2.4} /> You're all caught up.</p>
          ) : (
            <ul className="notif-list">
              {notes.map((n) => (
                <li key={n.id} className={`notif-item ${seen.includes(n.id) ? "" : "is-new"}`}>
                  <span className={`notif-ic ${n.kind} ${n.bad ? "bad" : ""}`}><Icon name={n.icon} size={17} /></span>
                  <button className="notif-body" onClick={() => { markOne(n.id); setOpen(false); setView(n.view || "overview"); }}>
                    <strong>{n.title}</strong>
                    <span>{n.detail}</span>
                  </button>
                  {n.change && onPreview && (
                    <button className={`notif-try ${isOn(n.change) ? "is-on" : ""}`} onClick={() => { markOne(n.id); onPreview(n.change); }}
                      aria-pressed={isOn(n.change)} title={isOn(n.change) ? "Remove from the forecast" : "Try it on the forecast"}>
                      {isOn(n.change) ? <><Icon name="check" size={14} stroke={2.6} /> On chart</> : "Try it"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!memory && <p className="notif-foot">Memory is off, so the actions based on how customers really pay are hidden.</p>}
        </div>
      )}
    </div>
  );
}

export function Topbar({ biz, user, businesses, onSwitch, onAdd, onSignOut, view, setView, dark, setDark, memory, setMemory,
  fc, actions, previewing = [], onPreview, smart }) {
  const name = user?.name || biz?.owner || "";
  const first = name.split(" ")[0] || "there";
  const initials = (name || "C W").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <header className="topbar">
      <div className="hello">
        <span className="avatar" aria-hidden="true">{initials}</span>
        <div>
          <p className="hello-name">Hello, {first}</p>
          <BusinessMenu biz={biz} businesses={businesses} onSwitch={onSwitch} onAdd={onAdd} onSignOut={onSignOut} />
        </div>
      </div>
      <div className="pills" role="tablist" aria-label="Views">
        {VIEWS.filter(([k]) => PILLS.includes(k)).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={view === k} className="pill" onClick={() => setView(k)}>
            {label}
          </button>
        ))}
      </div>
      <div className="top-actions">
        <MemorySwitch memory={memory} setMemory={setMemory} compact />
        <Notifications biz={biz} fc={fc} actions={actions} memory={memory} previewing={previewing}
          onPreview={onPreview} setView={setView} smart={smart} />
        <button className="round magnet" onClick={() => setView("memory")} aria-label="Search memory">
          <Icon name="search" />
        </button>
        <ThemeSwitch dark={dark} setDark={setDark} />
      </div>
    </header>
  );
}

// The agent mascot lives in its own file.
export { default as Mascot } from "./Mascot.jsx";
