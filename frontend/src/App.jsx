import { useCallback, useEffect, useState } from "react";
import { api, session } from "./api.js";
import Auth from "./components/Auth.jsx";
import Pointer from "./components/Pointer.jsx";
import Dashboard from "./Dashboard.jsx";
import { SharedReport } from "./components/ReportDoc.jsx";
import Landing from "./components/Landing.jsx";
import Legal from "./components/Legal.jsx";
import Icon from "./icons.jsx";

function initialDark() {
  try {
    const saved = localStorage.getItem("cashwise-theme");
    if (saved) return saved === "dark";
  } catch { /* storage unavailable */ }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

function AddBusiness({ onClose, onCreated }) {
  const [f, setF] = useState({ name: "", city: "", industry: "", with_demo_data: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try { onCreated(await api.addBusiness(f)); } catch (err) { setError(err.message); setBusy(false); }
  }
  return (
    <div className="modal-back" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal card" role="dialog" aria-modal="true" aria-labelledby="add-biz">
        <div className="card-head">
          <h2 id="add-biz">Add a business</h2>
          <button className="round small" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        <p className="sub">Each business has its own records and its own memory.</p>
        <form className="form" onSubmit={submit}>
          <label>Business name<input value={f.name} onChange={set("name")} required autoFocus /></label>
          <div className="two">
            <label>City<input value={f.city} onChange={set("city")} /></label>
            <label>What you sell<input value={f.industry} onChange={set("industry")} /></label>
          </div>
          <label className="check-row"><input type="checkbox" checked={f.with_demo_data} onChange={set("with_demo_data")} />
            Fill it with demo data</label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn btn-dark wide" disabled={busy}>{busy ? "Creating…" : "Create business"}</button>
        </form>
      </div>
    </div>
  );
}

// After "Sign in with Google/GitHub/Apple" the backend sends the browser back with #token=... or #signin_error=...
function readReturn() {
  const h = new URLSearchParams(window.location.hash.slice(1));
  const out = { token: h.get("token"), error: h.get("signin_error") };
  if (out.token || out.error) window.history.replaceState(null, "", window.location.pathname + window.location.search);
  if (out.token) session.signIn(out.token);
  return out;
}
const RETURN = readReturn();

// Three pages: the overview at /, sign in at /signin (or /signup), and the app at /app.
const pathOf = () => window.location.pathname.replace(/\/+$/, "") || "/";
const TITLES = { "/": "Cashwise · Know your cash before the week starts", "/signin": "Sign in · Cashwise",
  "/signup": "Create your account · Cashwise", "/app": "Cashwise",
  "/privacy": "Privacy policy · Cashwise", "/terms": "Terms of use · Cashwise" };

// A read-only report link: /r/<token>. Shown to anyone, signed in or not, with nothing else from the app.
const SHARED = window.location.pathname.match(/^\/r\/([A-Za-z0-9_-]+)\/?$/)?.[1];

export default function App() {
  if (SHARED) return <SharedReport token={SHARED} />;
  return <MainApp />;
}

function MainApp() {
  const [dark, setDark] = useState(initialDark);
  const [user, setUser] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [businessId, setBusinessId] = useState(session.businessId);
  const [checking, setChecking] = useState(!!session.token);
  const [adding, setAdding] = useState(false);
  const [path, setPath] = useState(() => (RETURN.token ? "/app" : RETURN.error ? "/signin" : pathOf()));

  const go = useCallback((to, { replace = false } = {}) => {
    if (to !== window.location.pathname) window.history[replace ? "replaceState" : "pushState"](null, "", to);
    setPath(to);
    window.scrollTo({ top: 0 });
  }, []);
  useEffect(() => {
    if (window.location.pathname !== path) window.history.replaceState(null, "", path);
    const back = () => setPath(pathOf());
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { document.title = TITLES[path] || TITLES["/"]; }, [path]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("cashwise-theme", dark ? "dark" : "light"); } catch { /* ignore */ }
  }, [dark]);

  const choose = useCallback((id) => { session.useBusiness(id); setBusinessId(id); }, []);

  const start = useCallback((s) => {
    setUser(s.user);
    setBusinesses(s.businesses);
    const keep = s.businesses.find((b) => b.id === session.businessId);
    choose(keep ? keep.id : s.businesses[0]?.id ?? null);
  }, [choose]);

  // Restore a previous sign-in.
  useEffect(() => {
    if (!session.token) return;
    api.me().then(start).catch(() => session.signOut()).finally(() => setChecking(false));
  }, [start]);

  useEffect(() => session.onExpired(() => { setUser(null); setBusinesses([]); setBusinessId(null); }), []);

  function signedIn(s) { session.signIn(s.token); start(s); go("/app"); }
  function signOut() { session.signOut(); setUser(null); setBusinesses([]); setBusinessId(null); go("/"); }
  async function created(b) {
    setAdding(false);
    setBusinesses(await api.businesses());
    choose(b.id);
  }

  const page = path === "/signin" || path === "/signup" ? "auth" : path === "/app" ? "app"
    : path === "/privacy" || path === "/terms" ? "legal" : "landing";
  // signed in people go straight past the sign-in page; signed out people can't see the app
  useEffect(() => {
    if (checking) return;
    if (page === "auth" && user) go("/app", { replace: true });
    if (page === "app" && !user) go("/signin", { replace: true });
  }, [page, user, checking, go]);

  if (checking && page !== "landing" && page !== "legal") return <div className="boot"><span className="dots" aria-label="Loading"><i /><i /><i /></span></div>;

  return (
    <>
      <Pointer />
      {page === "legal" ? (
        <Legal page={path.slice(1)} dark={dark} setDark={setDark} signedIn={!!user}
          onHome={() => go("/")} onSignIn={() => go(user ? "/app" : "/signin")} />
      ) : page === "landing" ? (
        <Landing dark={dark} setDark={setDark} signedIn={!!user} onSignIn={() => go(user ? "/app" : "/signin")}
          onSignUp={() => go(user ? "/app" : "/signup")} onSignedIn={signedIn} />
      ) : !user ? (
        <Auth onSignedIn={signedIn} dark={dark} setDark={setDark} initialError={RETURN.error || ""}
          initialMode={path === "/signup" ? "register" : "signin"} onHome={() => go("/")}
          onModeChange={(m) => go(m === "register" ? "/signup" : "/signin", { replace: true })} />
      ) : !businessId ? (
        <div className="boot">
          <p>You don't have a business yet.</p>
          <button className="btn btn-dark" onClick={() => setAdding(true)}>Add a business</button>
        </div>
      ) : (
        <Dashboard key={businessId} user={user} businesses={businesses} onSwitch={choose} onAdd={() => setAdding(true)}
          onSignOut={signOut} dark={dark} setDark={setDark} />
      )}
      {adding && <AddBusiness onClose={() => setAdding(false)} onCreated={created} />}
    </>
  );
}
