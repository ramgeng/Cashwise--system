import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { Logo, Mascot, ThemeSwitch } from "./Shell.jsx";

/*
  The overview page: what Cashwise is, who it's for, what's different, how it helps, and every feature,
  shown with real screenshots of the app (light or dark, to match the theme).
  The Sign in button stays in the top corner the whole way down, and there's another in the first screen.
*/
const DEMO = { email: "demo@cashwise.app", password: "demo1234" };
const NAV = [["tour", "Product"], ["features", "Features"], ["who", "Who it's for"], ["different", "Why Cashwise"], ["faq", "FAQ"]];

const INDUSTRIES = ["Electronics wholesale", "Pharma distribution", "Textiles and garments", "Auto parts", "FMCG distributors",
  "Hardware and tools", "Packaging", "Building materials", "Agencies and studios", "Contract manufacturing", "Food processing", "IT services"];

const TOUR = [
  { key: "overview", label: "Overview", icon: "home", title: "Your whole cash picture on one screen",
    text: "Cash in the bank, net cash flow for the next 4 weeks in three scenarios, your financial position, and what to do this week.",
    points: ["Best, likely and worst case", "Matched to your real bank balance", "Who owes you and what you owe"] },
  { key: "forecast", label: "Cash forecast", icon: "chart", title: "See the dip before it happens",
    text: "A day-by-day forecast from how each customer really pays, next to what a due-date dashboard would have told you.",
    points: ["Range of outcomes, not one guess", "Try what-ifs and watch the line move", "The AI agent explains it in plain words"] },
  { key: "alerts", label: "Smart alerts", icon: "shield", title: "Warnings while there's still time",
    text: "Low cash warnings, cash-flow risks and unusual expenses, sorted by how urgent they are, each with a button to act on it.",
    points: ["Your own safety buffer", "Slow payers and money stuck overdue", "Expense spikes and heavy months"] },
  { key: "customers", label: "Who owes you", icon: "users", title: "Know every customer's real habits",
    text: "How late each customer usually pays, whether they're getting slower, and the chance each invoice arrives in time.",
    points: ["Learned from their last 8 invoices", "Trend: faster, slower or steady", "Ranked by what's at risk"] },
  { key: "report", label: "Reports", icon: "file", title: "Reports management actually reads",
    text: "One click makes a clean report you can print, email, schedule weekly or monthly, or share as a secure read-only link.",
    points: ["Print or save as PDF", "Scheduled email to management", "Links that expire, with an audit trail"] },
  { key: "compare", label: "Compare", icon: "columns", title: "This month against last month",
    text: "Money in and out, net cash flow, invoicing, how fast customers paid, and expenses by category, side by side.",
    points: ["Any two periods", "Green for better, red for worse", "Expenses by category"] },
];

const WHO = [
  ["users", "Wholesalers and distributors", "You sell to shops on 30 to 60 days' credit and pay big suppliers on fixed dates."],
  ["receipt", "Manufacturers and traders", "Raw material bills arrive before customer money does. One slow payer leaves you short."],
  ["file", "Service businesses that invoice", "Agencies, contractors and consultants with salaries and rent going out on time."],
  ["scale", "Accountants and finance managers", "You report cash every week and want numbers you can explain line by line."],
  ["home", "Owners with more than one business", "Each business keeps its own records and memory. Switch in one click."],
];

const DIFF = [
  ["Assumes every customer pays on the due date", "Learns how each customer really pays from their last 8 invoices"],
  ["One number, as if the future were certain", "Best case, likely and worst case, side by side"],
  ["Forgets what happened last time", "Remembers what worked: who pays after a call, which supplier agreed to split a bill"],
  ["AI that can make up figures", "The AI never does the maths. Every number comes from the forecast engine and can be checked"],
  ["Tells you there's a problem on the day", "Warns you weeks ahead, with Smart alerts and a short list of what to do"],
  ["Generic charts", "Specific actions: who to chase, how much to ask a supplier to take now, and what that changes"],
];

const HELPS = [
  ["alert", "See a shortfall weeks early", "Know on Monday that Friday's bill won't be covered, while there's still time."],
  ["phone", "Know who to chase first", "Ranked by what's at risk and how each customer really behaves."],
  ["handshake", "Negotiate before the crunch", "Ask a supplier to take part now, and see exactly what it changes."],
  ["sparkle", "Decide in seconds", "Ask \"Can I pay Vertex on Friday?\" and get the answer with the numbers."],
  ["mail", "Keep management informed", "Weekly or monthly reports, emailed or shared as a secure link."],
  ["brain", "Get sharper every month", "Each outcome you record makes next month's advice better."],
];

const STEPS = [
  ["upload", "Bring your records", "Upload customers, invoices, payments and bills as CSV from Tally, Zoho Books or Excel, or start with the demo."],
  ["chart", "See what's really coming", "Cashwise learns each customer's real payment habits and forecasts your cash in three scenarios."],
  ["handshake", "Act, then record what happened", "Chase, negotiate, decide. The outcome goes into memory, so next month's advice is better."],
];

const FAQ = [
  ["Do I need accounting software?", "No. Any CSV works: an export from Tally, Zoho Books or QuickBooks, or a simple Excel sheet. Templates for every file are on the Your data page."],
  ["Does the AI make up numbers?", "No. Every figure comes from a forecast engine that works from your records, and you can trace each one. The AI explains the numbers, suggests what to do and remembers outcomes, but never does the arithmetic."],
  ["What does \"memory\" mean here?", "Cashwise keeps a long-term memory for each business: how customers paid, calls that worked, deals with suppliers. When you ask a question, it recalls what's relevant, so its advice fits your business, not businesses in general."],
  ["Is my data safe?", "Each business is stored in its own separate database, so one business can never see another's records. Shared report links can't be guessed, can expire, and can be turned off. Every financial change is recorded in the audit trail."],
  ["Can I use it on my phone?", "Yes. Every page works on a phone, including reports and alerts."],
  ["Is this financial advice?", "No. Cashwise gives you cash-flow insights to help you decide. The decisions stay yours."],
];

// A real screenshot of the app, in the current theme.
function Shot({ name, dark, alt, eager = false, className = "" }) {
  const dims = { agent: [560, 1179], notif: [640, 903], mobile: [520, 1125] }[name] || [1600, 1000];
  return (
    <img className={`lp-shot ${className}`} src={`/shots/${name}-${dark ? "dark" : "light"}.webp`} alt={alt}
      width={dims[0]} height={dims[1]} loading={eager ? "eager" : "lazy"} decoding="async" draggable="false" />
  );
}

function Frame({ children, url = "cashwise.app/app", className = "" }) {
  return (
    <div className={`lp-frame ${className}`}>
      <div className="lp-frame-bar" aria-hidden="true">
        <i /><i /><i />
        <span>{url}</span>
      </div>
      {children}
    </div>
  );
}

// Fade each section in as it scrolls into view (skipped for people who prefer less motion).
function useReveal(root) {
  useEffect(() => {
    const els = root.current?.querySelectorAll(".lp-reveal") || [];
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (calm || !("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [root]);
}

// The hero screenshot starts tilted back and lies flat as you scroll.
function useTilt(ref) {
  useEffect(() => {
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const el = ref.current;
    if (!el || calm) { el?.style.setProperty("--t", "0"); return; }
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const p = Math.min(1, Math.max(0, (window.innerHeight - r.top) / (window.innerHeight * 0.9)));
        el.style.setProperty("--t", (1 - p).toFixed(3));
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { window.removeEventListener("scroll", on); window.removeEventListener("resize", on); cancelAnimationFrame(raf); };
  }, [ref]);
}

function Tour({ dark }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (paused || calm) return;
    const t = setTimeout(() => setI((n) => (n + 1) % TOUR.length), 6500);
    return () => clearTimeout(t);
  }, [i, paused]);
  const s = TOUR[i];
  return (
    <div className="lp-tour lp-reveal" ref={box} onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
      <div className="lp-tabs" role="tablist" aria-label="Product tour">
        {TOUR.map((t, k) => (
          <button key={t.key} role="tab" aria-selected={k === i} className={`lp-tab ${k === i ? "is-on" : ""} ${paused ? "is-paused" : ""}`}
            onClick={() => { setI(k); setPaused(true); }}>
            <Icon name={t.icon} size={16} /> {t.label}
            {k === i && <span className="lp-tab-bar" key={`${i}-${paused}`} />}
          </button>
        ))}
      </div>
      <div className="lp-tour-body">
        <div className="lp-tour-text" key={s.key}>
          <h3>{s.title}</h3>
          <p>{s.text}</p>
          <ul>{s.points.map((p) => <li key={p}><Icon name="check" size={15} stroke={2.6} /> {p}</li>)}</ul>
        </div>
        <Frame className="lp-tour-frame">
          <div className="lp-tour-stack">
            {TOUR.map((t, k) => (
              <Shot key={t.key} name={t.key} dark={dark} alt={`Cashwise ${t.label} screen`} className={k === i ? "is-on" : ""} />
            ))}
          </div>
        </Frame>
      </div>
    </div>
  );
}

export default function Landing({ dark, setDark, signedIn, onSignIn, onSignUp, onSignedIn }) {
  const root = useRef(null);
  const hero = useRef(null);
  useReveal(root);
  useTilt(hero);
  const [scrolled, setScrolled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 10);
    on(); window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  async function demo() {
    if (signedIn) { onSignIn(); return; }
    setBusy(true); setErr("");
    try { onSignedIn(await api.login(DEMO.email, DEMO.password)); }
    catch (e) { setErr(e.message); setBusy(false); }
  }
  const jump = (id) => (e) => {
    e.preventDefault(); setMenu(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const signLabel = signedIn ? "Open dashboard" : "Sign in";

  return (
    <div className="lp" ref={root}>
      <div className="lp-aurora" aria-hidden="true"><i /><i /><i /></div>

      {/* ------------------------------------------------ header: Sign in is always here */}
      <header className={`lp-top ${scrolled ? "is-scrolled" : ""}`}>
        <div className="lp-top-in">
          <a className="lp-brand" href="/" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
            <Logo on="auto" size={34} /><span>Cashwise</span>
          </a>
          <nav className={`lp-nav ${menu ? "is-open" : ""}`} aria-label="Sections">
            {NAV.map(([id, label]) => <a key={id} href={`#${id}`} onClick={jump(id)}>{label}</a>)}
          </nav>
          <div className="lp-top-actions">
            <ThemeSwitch dark={dark} setDark={setDark} />
            <button className="round small lp-burger" onClick={() => setMenu(!menu)} aria-expanded={menu} aria-label="Sections">
              <Icon name={menu ? "x" : "chevron"} size={16} />
            </button>
            {!signedIn && <button className="lp-ghost lp-hide-sm" onClick={onSignUp}>Create account</button>}
            <button className="lp-btn lp-signin" onClick={onSignIn}>{signLabel} <Icon name="arrowUpRight" size={15} stroke={2.4} /></button>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------ hero */}
      <section className="lp-hero">
        <button className="lp-pill lp-reveal" onClick={jump("tour")}>
          <span>New</span> Smart alerts, scheduled reports and secure share links <Icon name="arrowUpRight" size={14} stroke={2.4} />
        </button>
        <h1 className="lp-reveal">Know if you can pay next week's bills, <em>before the week starts.</em></h1>
        <p className="lp-lead lp-reveal">
          Cashwise learns how each of your customers really pays, forecasts your cash in best, likely and worst cases,
          and remembers what worked last time. See a shortfall weeks ahead, and know exactly what to do about it.
        </p>
        <div className="lp-ctas lp-reveal">
          <button className="lp-btn lp-big" onClick={onSignIn}>{signLabel} <Icon name="arrowUpRight" size={18} stroke={2.4} /></button>
          <button className="lp-ghost lp-big" onClick={demo} disabled={busy}>
            <Icon name="play" size={15} /> {busy ? "Opening…" : "Try the live demo"}
          </button>
        </div>
        {!signedIn && <p className="lp-small lp-reveal">New here? <button className="link" onClick={onSignUp}>Create a free account</button> and bring your own records.</p>}
        {err && <p className="error" role="alert">{err}</p>}
        <ul className="lp-trust lp-reveal">
          <li><Icon name="check" size={14} stroke={2.8} /> Numbers you can check, never guessed by AI</li>
          <li><Icon name="check" size={14} stroke={2.8} /> Built for ₹, lakhs and Tally exports</li>
          <li><Icon name="check" size={14} stroke={2.8} /> Each business kept separate</li>
        </ul>

        <div className="lp-hero-visual" ref={hero}>
          <Frame className="lp-hero-frame">
            <Shot name="overview" dark={dark} alt="The Cashwise dashboard: cash in bank, net cash flow, financial position and the AI agent" eager />
          </Frame>
          <div className="lp-float lp-float-notif" aria-hidden="true"><Shot name="notif" dark={dark} alt="" eager /></div>
          <div className="lp-float lp-float-phone" aria-hidden="true"><Shot name="mobile" dark={dark} alt="" eager /></div>
          <div className="lp-float lp-float-chip" aria-hidden="true">
            <span className="lp-chip-ic"><Icon name="alert" size={16} /></span>
            <div><strong>₹1.94 L short on 13 Nov</strong><span>spotted 8 days early</span></div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ industries */}
      <section className="lp-marquee" aria-label="Built for businesses like these">
        <p>Built for businesses that sell on credit</p>
        <div className="lp-marquee-track">
          {[0, 1].map((n) => (
            <ul key={n} aria-hidden={n === 1}>
              {INDUSTRIES.map((x) => <li key={x}><Icon name="sparkle" size={12} /> {x}</li>)}
            </ul>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ the problem */}
      <section className="lp-sec lp-problem">
        <div className="lp-head lp-reveal">
          <p className="lp-kicker">The problem</p>
          <h2>Your dashboard says you're fine. <span>Your customers disagree.</span></h2>
          <p>Most cash dashboards assume every invoice is paid on its due date. In real life some customers are always
            a week or two late, and you find out on the day the big bill is due.</p>
        </div>
        <div className="lp-story lp-reveal">
          <p className="lp-story-set">The demo business has <strong>₹12.00 L</strong> in the bank and owes a supplier <strong>₹15 L on Friday 13 Nov</strong>.</p>
          <div className="lp-story-cards">
            <div className="lp-sc"><span>A due-date dashboard says</span><strong className="pos">₹9.91 L left</strong><em>assumes everyone pays on time</em></div>
            <span className="lp-sc-arrow"><Icon name="arrowUpRight" size={18} stroke={2.4} /></span>
            <div className="lp-sc is-key"><span>Cashwise says</span><strong className="neg">₹1.94 L short</strong><em>likely, from how each customer really pays</em></div>
            <span className="lp-sc-arrow"><Icon name="arrowUpRight" size={18} stroke={2.4} /></span>
            <div className="lp-sc"><span>Ask the supplier to take ₹12 L now</span><strong className="pos">₹1.06 L left</strong><em>the rest in two weeks: sorted</em></div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ product tour */}
      <section className="lp-sec" id="tour">
        <div className="lp-head lp-center lp-reveal">
          <p className="lp-kicker">Product tour</p>
          <h2>See it in action.</h2>
          <p>Real screens from the demo business. Click a tab, or let it play.</p>
        </div>
        <Tour dark={dark} />
      </section>

      {/* ------------------------------------------------ features (bento) */}
      <section className="lp-sec" id="features">
        <div className="lp-head lp-center lp-reveal">
          <p className="lp-kicker">Features</p>
          <h2>Everything you need to stay ahead of your cash.</h2>
        </div>
        <div className="lp-bento">
          <article className="lp-tile t-agent lp-reveal">
            <div className="lp-tile-text">
              <span className="lp-ic"><Icon name="brain" size={20} /></span>
              <h3>An AI agent with memory</h3>
              <p>Ask in plain words. It recalls what happened with each customer and supplier, quotes the forecast's numbers,
                and learns from every outcome you record.</p>
              <span className="lp-mascot"><Mascot tips={["Ask me: can I pay Vertex on Friday?", "I remember who pays after a call.", "I never make up numbers."]} sleepAfter={0} /></span>
            </div>
            <div className="lp-tile-shot"><Shot name="agent" dark={dark} alt="The AI agent answering: can I pay Vertex on Friday?" /></div>
          </article>

          <article className="lp-tile t-flow lp-reveal" style={{ "--d": "60ms" }}>
            <span className="lp-ic"><Icon name="wallet" size={20} /></span>
            <h3>Net cash flow, three ways</h3>
            <p>Money in minus money out over the next 4 weeks.</p>
            <div className="lp-mini-scen">
              <div><span>Best</span><strong className="neg">−₹9.98 L</strong></div>
              <div className="on"><span>Likely</span><strong className="neg">−₹11.98 L</strong></div>
              <div><span>Worst</span><strong className="neg">−₹16.73 L</strong></div>
            </div>
          </article>

          <article className="lp-tile t-notif lp-reveal" style={{ "--d": "120ms" }}>
            <span className="lp-ic"><Icon name="bell" size={20} /></span>
            <h3>Smart alerts and notifications</h3>
            <p>Low cash, cash-flow risks and unusual expenses, with a one-tap way to try each fix.</p>
            <div className="lp-tile-peek"><Shot name="notif" dark={dark} alt="The notification panel" /></div>
          </article>

          <article className="lp-tile t-pos lp-reveal">
            <span className="lp-ic"><Icon name="scale" size={20} /></span>
            <h3>Financial position</h3>
            <div className="lp-eq">
              <span><em>Cash</em>₹12.00 L</span><b>+</b><span><em>Owed to you</em>₹33.52 L</span><b>−</b>
              <span><em>You owe</em>₹33.30 L</span><b>=</b><span className="net"><em>Net</em>₹12.22 L</span>
            </div>
          </article>

          <article className="lp-tile t-whatif lp-reveal" style={{ "--d": "60ms" }}>
            <span className="lp-ic"><Icon name="handshake" size={20} /></span>
            <h3>What-if and This week</h3>
            <p>Tick an action or move a slider, and the forecast redraws instantly.</p>
            <div className="lp-ba">
              <div><span>Likely on 13 Nov</span><strong className="neg">₹1.94 L short</strong></div>
              <span className="lp-ba-step"><Icon name="check" size={14} stroke={2.8} /> Ask Vertex to take ₹12 L now</span>
              <div className="after"><span>With that one call</span><strong>₹1.06 L left</strong></div>
            </div>
          </article>

          <article className="lp-tile t-reports lp-reveal" style={{ "--d": "120ms" }}>
            <span className="lp-ic"><Icon name="file" size={20} /></span>
            <h3>Reports for management</h3>
            <ul className="lp-ticks">
              <li><Icon name="printer" size={15} /> Print or save as PDF</li>
              <li><Icon name="mail" size={15} /> Email, now or weekly and monthly</li>
              <li><Icon name="link" size={15} /> Read-only links that expire</li>
              <li><Icon name="columns" size={15} /> Compare any two periods</li>
              <li><Icon name="history" size={15} /> Audit trail of every change</li>
            </ul>
            <div className="lp-tile-peek lp-peek-report"><Shot name="report" dark={dark} alt="A cash-flow report ready to print" /></div>
          </article>

          <article className="lp-tile t-phone lp-reveal">
            <div className="lp-tile-text">
              <span className="lp-ic"><Icon name="phone" size={20} /></span>
              <h3>Works on your phone</h3>
              <p>Every page, from alerts to reports, on any screen.</p>
            </div>
            <div className="lp-tile-phone"><Shot name="mobile" dark={dark} alt="Cashwise on a phone" /></div>
          </article>

          <article className="lp-tile t-data lp-reveal" style={{ "--d": "60ms" }}>
            <span className="lp-ic"><Icon name="upload" size={20} /></span>
            <h3>Your data, your way</h3>
            <p>CSV uploads from Tally, Zoho Books or Excel, with templates, Indian dates and ₹ amounts. Every row is checked before anything is saved.</p>
            <div className="lp-tags"><span>Tally</span><span>Zoho Books</span><span>QuickBooks</span><span>Excel</span></div>
          </article>

          <article className="lp-tile t-bank lp-reveal" style={{ "--d": "120ms" }}>
            <span className="lp-ic"><Icon name="pencil" size={20} /></span>
            <h3>Matched to your bank</h3>
            <p>Type in what your bank shows. One adjustment keeps the books in line, and the audit trail records it.</p>
          </article>

          <article className="lp-tile t-multi lp-reveal" style={{ "--d": "180ms" }}>
            <span className="lp-ic"><Icon name="shield" size={20} /></span>
            <h3>Several businesses, kept apart</h3>
            <p>Each one has its own database and its own memory. Sign in with email, Google, GitHub or Apple.</p>
          </article>
        </div>
      </section>

      {/* ------------------------------------------------ who it's for */}
      <section className="lp-sec" id="who">
        <div className="lp-head lp-reveal">
          <p className="lp-kicker">Who it's for</p>
          <h2>For businesses that sell on credit <span>and pay bills on time.</span></h2>
          <p>If customers pay you later than you pay suppliers, salaries and rent, Cashwise is for you.</p>
        </div>
        <div className="lp-who">
          {WHO.map(([icon, title, text], i) => (
            <article key={title} className="lp-card lp-reveal" style={{ "--d": `${i * 60}ms` }}>
              <span className="lp-ic"><Icon name={icon} size={20} /></span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ what's different */}
      <section className="lp-sec" id="different">
        <div className="lp-split">
          <div className="lp-head lp-reveal">
            <p className="lp-kicker">Why Cashwise</p>
            <h2>Not another dashboard. <span>A companion that knows your customers.</span></h2>
            <p>Six things a usual cash dashboard gets wrong, and what Cashwise does instead.</p>
            <div className="lp-forecast-peek"><Frame url="cashwise.app/app · Cash forecast"><Shot name="forecast" dark={dark} alt="The cash forecast with best, likely and worst case and the due-date line" /></Frame></div>
          </div>
          <div className="lp-diff lp-reveal">
            {DIFF.map(([a, b]) => (
              <div className="lp-diff-row" key={a}>
                <p className="lp-no"><Icon name="x" size={14} stroke={2.8} /> {a}</p>
                <p className="lp-yes"><Icon name="check" size={14} stroke={2.8} /> {b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ how it helps */}
      <section className="lp-sec">
        <div className="lp-head lp-center lp-reveal">
          <p className="lp-kicker">How it helps</p>
          <h2>Fewer surprises. <span>Calmer Fridays.</span></h2>
        </div>
        <div className="lp-helps">
          {HELPS.map(([icon, title, text], i) => (
            <article key={title} className="lp-help lp-reveal" style={{ "--d": `${i * 50}ms` }}>
              <span className="lp-ic"><Icon name={icon} size={20} /></span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ how it works */}
      <section className="lp-sec" id="how">
        <div className="lp-head lp-center lp-reveal">
          <p className="lp-kicker">How it works</p>
          <h2>Up and running in about ten minutes.</h2>
        </div>
        <ol className="lp-steps">
          {STEPS.map(([icon, title, text], i) => (
            <li key={title} className="lp-step lp-reveal" style={{ "--d": `${i * 90}ms` }}>
              <span className="lp-num">0{i + 1}</span>
              <span className="lp-ic"><Icon name={icon} size={20} /></span>
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ------------------------------------------------ trust */}
      <section className="lp-sec">
        <div className="lp-trustbox lp-reveal">
          <div>
            <p className="lp-kicker">Built to be trusted</p>
            <h2>Every number is explainable.</h2>
            <p>Forecasts come from your records with clear rules: each customer's last 8 paid invoices give the 20th, 50th and
              90th percentile of how late they pay. The AI explains and suggests, and its answers quote those numbers.</p>
          </div>
          <ul>
            <li><Icon name="shield" size={18} /> A separate database for every business</li>
            <li><Icon name="link" size={18} /> Read-only links that expire and can be turned off</li>
            <li><Icon name="history" size={18} /> An audit trail of every financial change</li>
            <li><Icon name="help" size={18} /> Insights to help you decide, not financial advice</li>
          </ul>
        </div>
      </section>

      {/* ------------------------------------------------ FAQ */}
      <section className="lp-sec lp-faq-sec" id="faq">
        <div className="lp-head lp-reveal">
          <p className="lp-kicker">Questions</p>
          <h2>Good to know.</h2>
          <p>Anything else? Open the demo and ask the agent.</p>
        </div>
        <div className="lp-faq lp-reveal">
          {FAQ.map(([q, a]) => (
            <details key={q}>
              <summary>{q}<span className="lp-faq-ic"><Icon name="plus" size={15} stroke={2.4} /></span></summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ last call */}
      <section className="lp-sec">
        <div className="lp-final lp-reveal">
          <div className="lp-final-text">
            <h2>See next month's cash today.</h2>
            <p>Open the demo business in one click, or sign in and bring your own records.</p>
            <div className="lp-ctas">
              <button className="lp-btn lp-big lp-on-green" onClick={onSignIn}>{signLabel} <Icon name="arrowUpRight" size={18} stroke={2.4} /></button>
              <button className="lp-ghost lp-big lp-on-green" onClick={demo} disabled={busy}><Icon name="play" size={15} /> Try the live demo</button>
            </div>
          </div>
          <div className="lp-final-shot" aria-hidden="true"><Shot name="alerts" dark={false} alt="" /></div>
        </div>
      </section>

      <footer className="lp-foot">
        <span className="lp-brand"><Logo on="auto" size={26} /><span>Cashwise</span></span>
        <p>Cash-flow insights to help you decide. Not financial advice.</p>
        <button className="link" onClick={onSignIn}>{signLabel}</button>
      </footer>
    </div>
  );
}
