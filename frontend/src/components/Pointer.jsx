import { useEffect, useRef } from "react";

/*
  Cursor interactions, handled by one pointer listener for the whole page:
  - a soft green glow around the cursor. It is moved on the pointer event itself,
    with no easing, so it stays exactly on the cursor (no delay).
  - a spotlight inside any .card under the cursor (CSS vars --mx / --my)
  - a gentle 3D tilt on .tilt cards, and .magnet buttons lean towards the cursor
  Turned off for touch screens and for people who prefer reduced motion.
*/
export default function Pointer() {
  const glow = useRef(null);

  useEffect(() => {
    const fine = window.matchMedia?.("(pointer: fine)").matches;
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) return;

    let lastCard = null, lastTilt = null, lastMagnet = null;
    const reset = (el, props) => el && props.forEach((p) => el.style.removeProperty(p));

    function move(e) {
      const x = e.clientX, y = e.clientY;
      if (glow.current) {
        glow.current.style.transform = `translate3d(${x - 200}px, ${y - 200}px, 0)`;
        glow.current.classList.add("on");
      }

      const t = e.target instanceof Element ? e.target : null;

      const card = t?.closest(".card");
      if (card !== lastCard) { lastCard?.classList.remove("is-lit"); lastCard = card; card?.classList.add("is-lit"); }
      if (card) {
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${x - r.left}px`);
        card.style.setProperty("--my", `${y - r.top}px`);
      }

      const tilt = t?.closest(".tilt");
      if (tilt !== lastTilt) { reset(lastTilt, ["--rx", "--ry"]); lastTilt = tilt; }
      if (tilt) {
        const r = tilt.getBoundingClientRect();
        const px = (x - r.left) / r.width - 0.5, py = (y - r.top) / r.height - 0.5;
        tilt.style.setProperty("--rx", `${(-py * 4).toFixed(2)}deg`);
        tilt.style.setProperty("--ry", `${(px * 5).toFixed(2)}deg`);
      }

      const mag = t?.closest(".magnet");
      if (mag !== lastMagnet) { reset(lastMagnet, ["--tx", "--ty"]); lastMagnet = mag; }
      if (mag) {
        const r = mag.getBoundingClientRect();
        mag.style.setProperty("--tx", `${((x - r.left - r.width / 2) * 0.25).toFixed(1)}px`);
        mag.style.setProperty("--ty", `${((y - r.top - r.height / 2) * 0.3).toFixed(1)}px`);
      }
    }

    function leave() {
      glow.current?.classList.remove("on");
      lastCard?.classList.remove("is-lit");
      reset(lastTilt, ["--rx", "--ry"]); reset(lastMagnet, ["--tx", "--ty"]);
      lastCard = lastTilt = lastMagnet = null;
    }

    addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
    };
  }, []);

  return <div ref={glow} className="cursor-glow" aria-hidden="true" />;
}
