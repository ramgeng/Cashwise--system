import { useEffect, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { Logo, Mascot, ThemeSwitch } from "./Shell.jsx";

const DEMO = { email: "demo@cashwise.app", password: "demo1234" };

function BrandMark({ name }) {
  if (name === "google") {
    return (
      <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
      </svg>
    );
  }
  if (name === "github") {
    return (
      <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="currentColor">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor">
      <path d="M16.37 12.68c-.02-2.2 1.8-3.26 1.88-3.31-1.03-1.5-2.62-1.7-3.19-1.73-1.36-.14-2.65.8-3.34.8-.69 0-1.75-.78-2.88-.76-1.48.02-2.85.86-3.61 2.19-1.54 2.67-.39 6.62 1.1 8.79.73 1.06 1.6 2.25 2.74 2.21 1.1-.04 1.52-.71 2.85-.71 1.33 0 1.71.71 2.88.69 1.19-.02 1.94-1.08 2.66-2.15.84-1.23 1.19-2.42 1.21-2.48-.03-.01-2.32-.89-2.34-3.54zM14.18 6.2c.6-.73 1.01-1.75.9-2.76-.87.04-1.92.58-2.55 1.31-.56.65-1.05 1.69-.92 2.68.97.08 1.96-.49 2.57-1.23z" />
    </svg>
  );
}

// The product as one scene: forecast line on the background, glass panels floating over it,
// and the memory web behind. Everything fades into the panel colour at the edges.
const NODES = [[8, 18], [20, 8], [34, 20], [48, 10], [62, 22], [76, 12], [90, 24], [14, 40], [30, 46], [56, 42],
  [72, 50], [88, 44], [22, 66], [44, 70], [64, 74], [84, 68], [38, 32], [80, 32]];
const LINKS = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [0, 7], [7, 8], [8, 16], [16, 2], [16, 9], [9, 4],
  [9, 10], [10, 11], [11, 6], [17, 5], [17, 11], [8, 12], [12, 13], [13, 14], [14, 15], [10, 14], [15, 11]];

export function Scene() {
  return (
    <div className="scene" aria-hidden="true">
      <svg className="sc-web" viewBox="0 0 100 80" preserveAspectRatio="xMidYMid slice">
        {LINKS.map(([a, b], i) => (
          <line key={i} x1={NODES[a][0]} y1={NODES[a][1]} x2={NODES[b][0]} y2={NODES[b][1]} />
        ))}
        {NODES.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="0.45" style={{ animationDelay: `${(i % 6) * 0.5}s` }} />)}
      </svg>

      <svg className="sc-chart" viewBox="0 0 600 220" preserveAspectRatio="none">
        <defs>
          <linearGradient id="scband" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a6ffa6" stopOpacity=".34" />
            <stop offset="100%" stopColor="#a6ffa6" stopOpacity=".04" />
          </linearGradient>
        </defs>
        <path className="sc-band" d="M0 70 H70 V76 H150 V58 H230 V128 H300 V110 H380 V92 H460 V56 H600 V128 H460 V118 H380 V150 H300 V176 H230 V168 H150 V104 H70 V86 H0 Z" />
        <path className="sc-naive" d="M0 70 H70 V54 H150 V30 H230 V88 H300 V78 H380 V66 H460 V44 H600" />
        <line className="sc-zero" x1="0" x2="600" y1="150" y2="150" />
        <path className="sc-line" d="M0 70 H70 V82 H150 V80 H230 V158 H300 V146 H380 V122 H460 V86 H600" />
        <circle className="sc-dot" cx="230" cy="158" r="6" />
      </svg>

      <div className="glass g-answer">
        <p className="g-lead">After paying Vertex ₹15 L on Friday 13 Nov</p>
        <p className="g-big">₹1.94 L short</p>
        <p className="g-small">Likely. A due-date dashboard says <s>₹9.91 L left</s></p>
      </div>

      <div className="glass g-agent">
        <span className="g-bot"><Mascot interactive={false} sleepAfter={0} /></span>
        <p>Chase Mehta Traders today. They usually pay 12 days late in festival season.</p>
      </div>

      <div className="glass g-chip g-cust">
        <span className="g-bars"><i style={{ height: 6 }} /><i style={{ height: 16 }} className="late" /><i style={{ height: 18 }} className="late" /><i style={{ height: 8 }} /></span>
        <span><strong>Mehta Traders</strong> usually 12 days late</span>
      </div>

      <div className="glass g-chip g-mem">
        <Icon name="brain" size={15} /> <span><strong>43</strong> things remembered</span>
      </div>
    </div>
  );
}

export default function Auth({ onSignedIn, dark, setDark, initialError = "", initialMode = "signin", onHome, onModeChange }) {
  const [mode, setModeState] = useState(initialMode);
  const setMode = (m) => { setModeState(m); onModeChange?.(m); };
  const [f, setF] = useState({ name: "", email: "", password: "", business_name: "", city: "", industry: "", with_demo_data: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [providers, setProviders] = useState([
    { key: "google", label: "Google" }, { key: "github", label: "GitHub" }, { key: "apple", label: "Apple" }]);
  const [hint, setHint] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const [offline, setOffline] = useState("");
  useEffect(() => {
    api.providers().then((p) => { setProviders(p); setOffline(""); })
      .catch((e) => setOffline(e.status === 404
        ? "The backend is an older version. Restart it with: uvicorn app.main:app --reload"
        : e.message));
  }, []);

  async function submit(e, creds) {
    e?.preventDefault();
    setBusy(true); setError("");
    try {
      const s = mode === "signin" || creds
        ? await api.login((creds || f).email, (creds || f).password)
        : await api.register(f);
      onSignedIn(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function social(p) {
    setError("");
    if (p.configured) { window.location.href = `/api/auth/oauth/${p.key}/start`; return; }
    if (offline || p.configured === undefined) { setHint(offline || "Can't reach the backend."); return; }
    setHint(`${p.label} sign-in isn't set up yet. ${p.help || ""}`);
  }

  const signin = mode === "signin";
  return (
    <div className="auth">
      <section className="auth-side">
        <a className="logo logo-link" href="/" onClick={(e) => { if (onHome) { e.preventDefault(); onHome(); } }} aria-label="Cashwise overview">
          <Logo /><div><p className="logo-name">Cashwise</p><p className="logo-tag">Your AI cash-flow companion</p></div>
        </a>
        <Scene />
        <div className="auth-body">
        <div className="auth-pitch">
          <p className="pitch-big">Know if you can pay next week's bills, before the week starts.</p>
          <p className="pitch-sub">Cashwise learns how each of your customers really pays, and remembers what worked last time.</p>
        </div>
        <ul className="auth-points">
          <li><Icon name="users" size={17} /> Real payment habits, not due dates</li>
          <li><Icon name="chart" size={17} /> Best, likely and worst cash</li>
          <li><Icon name="brain" size={17} /> Gets sharper with every outcome</li>
        </ul>
        </div>
      </section>

      <section className="auth-main">
        <div className="auth-top">
          {onHome && (
            <a className="auth-back" href="/" onClick={(e) => { e.preventDefault(); onHome(); }}>
              <Icon name="chevron" size={14} stroke={2.4} /> Overview
            </a>
          )}
          <span className="auth-top-note">{signin ? "New to Cashwise?" : "Already have an account?"}</span>
          <button className="link" onClick={() => { setMode(signin ? "register" : "signin"); setError(""); }}>
            {signin ? "Create an account" : "Sign in"}
          </button>
          <ThemeSwitch dark={dark} setDark={setDark} />
        </div>

        <div className="auth-card">
          {offline && <p className="error offline" role="alert">{offline}</p>}
          <h1 className="auth-h">{signin ? "Welcome back" : "Set up your business"}</h1>
          <p className="auth-sub">{signin ? "Sign in to see this week's cash." : "Free to try. Upload your records, or start with demo data."}</p>

          <div className="social">
            {providers.map((p) => (
              <button key={p.key} type="button" className={`social-btn magnet ${p.configured === false ? "is-off" : ""}`}
                onClick={() => social(p)} aria-describedby={p.configured === false ? "social-hint" : undefined}>
                <BrandMark name={p.key} /> <span>{p.label}</span>
              </button>
            ))}
          </div>
          {hint && <p id="social-hint" className="hint social-hint" role="status">{hint}</p>}

          <p className="or"><span>or with email</span></p>

          <form onSubmit={submit} className="form">
            {!signin && (
              <>
                <div className="two">
                  <label>Your name<input value={f.name} onChange={set("name")} required autoComplete="name" /></label>
                  <label>Business name<input value={f.business_name} onChange={set("business_name")} required placeholder="Malabar Electronics" /></label>
                </div>
                <div className="two">
                  <label>City<input value={f.city} onChange={set("city")} placeholder="Kochi" /></label>
                  <label>What you sell<input value={f.industry} onChange={set("industry")} placeholder="Electronics wholesale" /></label>
                </div>
              </>
            )}
            <label>Email<input type="email" value={f.email} onChange={set("email")} required autoComplete="email" placeholder="you@business.com" /></label>
            <label>Password
              <input type="password" value={f.password} onChange={set("password")} required minLength={signin ? 1 : 8}
                autoComplete={signin ? "current-password" : "new-password"} placeholder={signin ? "" : "At least 8 characters"} />
            </label>
            {!signin && (
              <label className="check-row">
                <input type="checkbox" checked={f.with_demo_data} onChange={set("with_demo_data")} />
                Start with demo data so I can look around first
              </label>
            )}
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" className="btn btn-dark wide magnet" disabled={busy}>
              {busy ? "One moment…" : signin ? "Sign in" : "Create account"}
            </button>
          </form>

          {signin && (
            <button className="demo-strip magnet" onClick={() => submit(null, DEMO)} disabled={busy}>
              <span className="demo-ic"><Icon name="sparkle" size={18} /></span>
              <span><strong>Just looking?</strong> Open the demo business, Malabar Electronics</span>
              <Icon name="arrowUpRight" size={18} />
            </button>
          )}
        </div>

        <p className="auth-legal">Cashwise gives cash-flow insights to help you decide. It isn't financial advice.</p>
      </section>
    </div>
  );
}
