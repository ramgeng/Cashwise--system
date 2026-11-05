import { useEffect, useRef, useState } from "react";

/*
  The agent's mascot. It:
  - follows the cursor with its eyes and leans its head towards it
  - blinks at random (sometimes twice), and looks around when the cursor is still
  - smiles and blushes when hovered; jumps, sparkles and shares a tip when clicked
  - looks up and around while "thinking", looks down while you type ("listening")
  - dozes off after a while with no movement, and wakes when you come back
  Movement is skipped for people who prefer reduced motion.
*/

const DEFAULT_TIPS = [
  "Tick an action in This week to see it on the chart.",
  "Mehta Traders usually pays about 12 days late.",
  "Record what happened. I'll remember it next time.",
  "Switch memory off to see what a plain dashboard says.",
  "Ask me: can I pay Vertex on Friday?",
];

const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export default function Mascot({ talking = false, listening = false, tips = DEFAULT_TIPS, interactive = true,
  sleepAfter = 25000 }) {
  const svg = useRef(null);
  const head = useRef(null);
  const pupils = useRef(null);
  const antenna = useRef(null);
  const [hover, setHover] = useState(false);
  const [blink, setBlink] = useState(false);
  const [asleep, setAsleep] = useState(false);
  const [jump, setJump] = useState(0);
  const [tip, setTip] = useState(null);
  const tipIndex = useRef(0);

  const mood = asleep ? "sleepy" : talking ? "thinking" : hover || jump ? "happy" : listening ? "listening" : "idle";
  const moodRef = useRef(mood);
  moodRef.current = mood;

  // ---------------------------------------------------------------- follow the cursor
  useEffect(() => {
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (calm) return;
    const target = { x: 0, y: 0, lean: 0, lx: 0, ly: 0 };
    const now = { x: 0, y: 0, lean: 0, lx: 0, ly: 0, ant: 0 };
    let mouse = null, lastMove = performance.now(), wander = { x: 0, y: 0, until: 0 }, raf;

    const onMove = (e) => {
      mouse = { x: e.clientX, y: e.clientY };
      lastMove = performance.now();
      setAsleep(false);
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const frame = (t) => {
      const el = svg.current;
      if (el) {
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2, cy = r.top + r.height * 0.47;
        const m = moodRef.current;
        let dx = 0, dy = 0;
        if (m === "thinking") {                    // look up and around while working
          dx = Math.sin(t / 420) * 120; dy = -90 + Math.cos(t / 610) * 30;
        } else if (m === "listening") {            // look down at the message box
          dx = Math.sin(t / 900) * 20; dy = 160;
        } else if (m === "sleepy") {
          dx = 0; dy = 40;
        } else if (mouse && t - lastMove < 4000) {
          dx = mouse.x - cx; dy = mouse.y - cy;
        } else {                                   // cursor still: glance around now and then
          if (t > wander.until) {
            wander = Math.random() < 0.35 ? { x: (Math.random() - 0.5) * 300, y: (Math.random() - 0.5) * 160 }
              : { x: 0, y: 0 };
            wander.until = t + 1400 + Math.random() * 2200;
          }
          dx = wander.x; dy = wander.y;
        }
        const dist = Math.hypot(dx, dy) || 1;
        const reach = clamp(dist / 140, 0, 1);
        target.x = (dx / dist) * 6 * reach;
        target.y = (dy / dist) * 4.5 * reach;
        target.lean = clamp(dx / 45, -8, 8);
        target.lx = clamp(dx / 90, -3.5, 3.5);
        target.ly = clamp(dy / 120, -2.5, 2.5);

        const k = 0.14;
        now.x = lerp(now.x, target.x, k); now.y = lerp(now.y, target.y, k);
        now.lean = lerp(now.lean, target.lean, 0.08);
        now.lx = lerp(now.lx, target.lx, 0.08); now.ly = lerp(now.ly, target.ly, 0.08);
        now.ant = lerp(now.ant, -now.lean * 1.6, 0.05);   // antenna lags behind the head
        if (pupils.current) pupils.current.setAttribute("transform", `translate(${now.x.toFixed(2)} ${now.y.toFixed(2)})`);
        if (head.current) head.current.style.transform =
          `translate(${now.lx.toFixed(2)}px, ${now.ly.toFixed(2)}px) rotate(${now.lean.toFixed(2)}deg)`;
        if (antenna.current) antenna.current.style.transform = `rotate(${now.ant.toFixed(2)}deg)`;
        if (sleepAfter && t - lastMove > sleepAfter && moodRef.current === "idle") setAsleep(true);
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("pointermove", onMove); };
  }, [sleepAfter]);

  // ---------------------------------------------------------------- random blinks
  useEffect(() => {
    let alive = true, timer;
    const once = (then) => { setBlink(true); setTimeout(() => { setBlink(false); then?.(); }, 130); };
    const loop = () => {
      timer = setTimeout(() => {
        if (!alive) return;
        if (moodRef.current !== "sleepy") {
          Math.random() < 0.25 ? once(() => setTimeout(() => alive && once(), 170)) : once();
        }
        loop();
      }, 2200 + Math.random() * 3800);
    };
    loop();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  // ---------------------------------------------------------------- click: jump + tip
  function poke() {
    if (!interactive) return;
    setAsleep(false);
    setJump((n) => n + 1);
    if (tips?.length) {
      setTip(tips[tipIndex.current % tips.length]);
      tipIndex.current += 1;
    }
  }
  useEffect(() => {
    if (!jump) return;
    const t = setTimeout(() => setJump(0), 900);
    return () => clearTimeout(t);
  }, [jump]);
  useEffect(() => {
    if (!tip) return;
    const t = setTimeout(() => setTip(null), 3800);
    return () => clearTimeout(t);
  }, [tip]);

  const eyesShape = mood === "happy" ? "arc" : mood === "sleepy" ? "closed" : "round";
  const mouth = {
    idle: "M70 81q10 6 20 0",
    listening: "M72 82q8 4 16 0",
    happy: "M67 79q13 11 26 0",
    thinking: null,
    sleepy: "M73 83h14",
  }[mood];

  return (
    <span className={`mascot-wrap ${interactive ? "is-interactive" : ""}`}
      onPointerEnter={() => interactive && setHover(true)} onPointerLeave={() => setHover(false)}>
      <svg ref={svg} className={`mascot m-${mood} ${jump ? "is-jumping" : ""}`} viewBox="0 0 160 150"
        onClick={poke} onMouseDown={(e) => e.preventDefault()} role={interactive ? "button" : undefined} aria-hidden={interactive ? undefined : true}
        aria-label={interactive ? "Cashwise agent. Click for a tip." : undefined} tabIndex={interactive ? 0 : undefined}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); poke(); } }}>
        <defs>
          <radialGradient id="mg" cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity=".9" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
          <clipPath id="m-screen"><rect x="46" y="50" width="68" height="40" rx="18" /></clipPath>
        </defs>
        <circle className="m-glow" cx="80" cy="72" r="70" fill="url(#mg)" />

        <g className="m-float">
          <g className="m-jump">
            <g ref={head} className="m-head">
              <g ref={antenna} className="m-antenna">
                <line x1="80" y1="22" x2="80" y2="34" stroke="var(--ink-2)" strokeWidth="3" strokeLinecap="round" />
                <circle className="m-bulb" cx="80" cy="19" r="5" fill="var(--accent-strong)" />
              </g>
              <rect x="34" y="34" width="92" height="74" rx="30" fill="var(--card)" stroke="var(--line)" strokeWidth="2" />
              <rect x="26" y="60" width="12" height="24" rx="6" fill="var(--line)" />
              <rect x="122" y="60" width="12" height="24" rx="6" fill="var(--line)" />
              <rect x="46" y="50" width="68" height="40" rx="18" fill="#10261b" />

              <g clipPath="url(#m-screen)">
                <g className={`m-eyes ${blink ? "is-blink" : ""}`}>
                  {eyesShape === "round" && (
                    <g ref={pupils}>
                      <ellipse cx="66" cy="68" rx="6" ry="7" fill="var(--accent)" />
                      <ellipse cx="94" cy="68" rx="6" ry="7" fill="var(--accent)" />
                      <circle cx="68.2" cy="65.5" r="1.8" fill="#eafff0" />
                      <circle cx="96.2" cy="65.5" r="1.8" fill="#eafff0" />
                    </g>
                  )}
                  {eyesShape === "arc" && (
                    <g ref={pupils}>
                      <path d="M60 70q6-8 12 0" stroke="var(--accent)" strokeWidth="4" fill="none" strokeLinecap="round" />
                      <path d="M88 70q6-8 12 0" stroke="var(--accent)" strokeWidth="4" fill="none" strokeLinecap="round" />
                    </g>
                  )}
                  {eyesShape === "closed" && (
                    <g ref={pupils}>
                      <path d="M60 69q6 5 12 0" stroke="var(--accent)" strokeWidth="3.5" fill="none" strokeLinecap="round" />
                      <path d="M88 69q6 5 12 0" stroke="var(--accent)" strokeWidth="3.5" fill="none" strokeLinecap="round" />
                    </g>
                  )}
                </g>
                <ellipse className="m-cheek" cx="56" cy="80" rx="5" ry="3" />
                <ellipse className="m-cheek" cx="104" cy="80" rx="5" ry="3" />
                {mouth ? <path className="m-mouth" d={mouth} stroke="var(--accent)" strokeWidth="3" fill="none" strokeLinecap="round" />
                  : <circle className="m-mouth" cx="80" cy="82" r="3" fill="none" stroke="var(--accent)" strokeWidth="2.5" />}
              </g>
            </g>
            <rect x="52" y="112" width="56" height="26" rx="13" fill="var(--card)" stroke="var(--line)" strokeWidth="2" />
            <circle className="m-heart" cx="80" cy="125" r="5" fill="var(--accent-strong)" />
          </g>
        </g>

        <path className="m-spark" d="M134 30l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="var(--accent-strong)" />
        <path className="m-spark s2" d="M22 108l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="var(--accent-strong)" />

        {mood === "sleepy" && (
          <g className="m-zz" fill="var(--ink-2)" fontWeight="800" fontFamily="inherit">
            <text x="118" y="34" fontSize="12">z</text>
            <text x="128" y="22" fontSize="9">z</text>
          </g>
        )}
        {jump > 0 && (
          <g className="m-burst" key={jump} fill="var(--accent-strong)">
            {[[-46, -30], [44, -34], [-54, 8], [54, 4], [-22, -50], [24, -52]].map(([x, y], i) => (
              <path key={i} d="M0-5l1.5 3.5L5 0l-3.5 1.5L0 5l-1.5-3.5L-5 0l3.5-1.5z"
                style={{ "--bx": `${x}px`, "--by": `${y}px`, animationDelay: `${i * 25}ms` }} transform="translate(80 70)" />
            ))}
          </g>
        )}
      </svg>
      {tip && <span className="m-tip" role="status">{tip}</span>}
    </span>
  );
}
