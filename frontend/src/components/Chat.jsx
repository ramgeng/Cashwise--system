import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const STARTERS = [
  "Can I pay Vertex on Friday?",
  "Who should I chase first this week?",
  "What if Mehta pays 15 days late?",
  "What if I pay Vertex 10 lakh on Friday and the rest on 27 Nov?",
];

const SECTIONS = ["Answer", "Recommended actions", "Evidence", "Pattern from memory", "Assumptions & uncertainty"];

// Split the agent's reply into its labelled parts so each can be styled.
function parse(text) {
  const re = new RegExp(`^\\s*\\**(${SECTIONS.join("|")})\\**\\s*:\\**\\s*`, "i");
  const parts = [];
  let cur = { title: null, lines: [] };
  for (const line of (text || "").split("\n")) {
    const m = line.match(re);
    if (m) {
      if (cur.title || cur.lines.some((l) => l.trim())) parts.push(cur);
      cur = { title: SECTIONS.find((s) => s.toLowerCase() === m[1].toLowerCase()), lines: [line.slice(m[0].length)] };
    } else cur.lines.push(line);
  }
  parts.push(cur);
  return parts.map((p) => ({ ...p, body: p.lines.join("\n").replace(/\*\*/g, "").trim() })).filter((p) => p.body);
}

function Reply({ msg, memory }) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState("");

  async function send(helpful, text = "") {
    try {
      await api.feedback({ helpful, text, question: msg.question });
      setSaved(helpful ? "Saved. The agent will lean on this next time." : "Saved. The agent will avoid this next time.");
    } catch (e) {
      setSaved(e.message);
    }
  }

  return (
    <article className="reply">
      {parse(msg.answer).map((p, i) => (
        <div key={i} className={`part ${p.title === "Answer" ? "part-answer" : ""} ${p.title === "Pattern from memory" ? "part-memory" : ""}`}>
          {p.title && p.title !== "Answer" && <h4>{p.title}</h4>}
          <p>{p.body}</p>
        </div>
      ))}

      {(msg.tool_calls?.length > 0 || msg.memories_used?.length > 0) && (
        <button className="link" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide" : "Show"} how this was worked out ({msg.tool_calls?.length || 0} calculations
          {memory ? `, ${msg.memories_used?.length || 0} memories` : ""})
        </button>
      )}
      {open && (
        <div className="trace">
          {msg.tool_calls?.map((t, i) => (
            <p key={i}><code>{t.tool}</code> {JSON.stringify(t.args)}</p>
          ))}
          {msg.memories_used?.length > 0 && <h4>Remembered</h4>}
          {msg.memories_used?.map((m, i) => <p key={i} className="mem">{m}</p>)}
        </div>
      )}

      {memory && !saved && (
        <div className="rate">
          <span>Was this right for your business?</span>
          <button onClick={() => { setRating("up"); send(true); }}>Useful</button>
          <button onClick={() => setRating("down")} aria-pressed={rating === "down"}>Not right</button>
        </div>
      )}
      {rating === "down" && !saved && (
        <form className="note" onSubmit={(e) => { e.preventDefault(); send(false, note); }}>
          <label htmlFor={`note-${msg.id}`}>What should it do instead?</label>
          <input id={`note-${msg.id}`} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Never suggest delaying salaries" />
          <button type="submit">Save to memory</button>
        </form>
      )}
      {saved && <p className="saved">{saved}</p>}
    </article>
  );
}

export default function Chat({ memory }) {
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    if (msgs.length) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);

  async function ask(question) {
    if (!question.trim() || busy) return;
    setQ("");
    setBusy(true);
    const id = Date.now();
    setMsgs((m) => [...m, { id, role: "user", text: question, memory }]);
    try {
      const r = await api.ask(question, memory);
      setMsgs((m) => [...m, { id: id + 1, role: "agent", question, memory, ...r }]);
    } catch (e) {
      setMsgs((m) => [...m, { id: id + 1, role: "error", text: e.message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat" aria-label="Ask about your cash">
      <h2>Ask</h2>
      <div className="thread">
        {msgs.length === 0 && (
          <div className="starters">
            <p>Ask about any payment, customer or what-if. Numbers come from your records, never guessed.</p>
            {STARTERS.map((s) => <button key={s} onClick={() => ask(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m) =>
          m.role === "user" ? (
            <p key={m.id} className="you">{m.text}<span>{m.memory ? "" : "memory off"}</span></p>
          ) : m.role === "error" ? (
            <p key={m.id} className="error">{m.text}</p>
          ) : (
            <Reply key={m.id} msg={m} memory={m.memory} />
          )
        )}
        {busy && <p className="thinking">Checking your records{memory ? " and memory" : ""}…</p>}
        <div ref={end} />
      </div>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <label htmlFor="q" className="sr-only">Your question</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Can I pay Vertex on Friday?" disabled={busy} />
        <button type="submit" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </section>
  );
}
