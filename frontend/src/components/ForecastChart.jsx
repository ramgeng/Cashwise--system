import {
  Area, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { day, inr, shortInr } from "../format.js";

const PALETTE = {
  light: { ink: "#0F2A1E", band: "#2FBF5B", short: "#E5484D", muted: "#9AA8A0", grid: "#E3EAE5", whatif: "#4C7DFF", dot: "#FFFFFF" },
  dark: { ink: "#E8F3EC", band: "#A6FFA6", short: "#FF6B6B", muted: "#6E8578", grid: "#22352B", whatif: "#8FB4FF", dot: "#13201A" },
};

function Tip({ active, payload, label, memory, hasWhatIf }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{day(label)}</strong>
      {memory ? (
        <>
          <span>Likely {inr(d.likely)}</span>
          <span className="muted">Range {inr(d.worst)} to {inr(d.best)}</span>
          {hasWhatIf && d.whatif !== undefined && <span className="tip-whatif">With your what-if {inr(d.whatif)}</span>}
          <span className="muted">Due-date view {inr(d.naive)}</span>
        </>
      ) : (
        <span>Balance {inr(d.naive)}</span>
      )}
    </div>
  );
}

export default function ForecastChart({ data, memory, scenario, dark, height = 320 }) {
  const C = PALETTE[dark ? "dark" : "light"];
  const { days, target_date, key_bill, summary } = data;
  const hasWhatIf = memory && scenario?.days?.length;
  const wi = hasWhatIf ? Object.fromEntries(scenario.days.map((d) => [d.date, d.likely])) : {};
  const rows = days.map((d) => ({ ...d, range: [d.worst, d.best], whatif: wi[d.date] }));
  const low = memory ? summary.likely : summary.naive;

  return (
    <div className="chart-wrap">
      <div className="chart" style={{ height }} role="img"
        aria-label={`Cash forecast. Lowest ${memory ? "likely " : ""}balance ${inr(low.lowest)} on ${day(low.lowest_date)}.`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 26, right: 14, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.band} stopOpacity={dark ? 0.32 : 0.42} />
                <stop offset="100%" stopColor={C.band} stopOpacity={0.1} />
              </linearGradient>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation={dark ? 3 : 2} result="b" />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>
            <XAxis dataKey="date" tickFormatter={day} tick={{ fill: C.muted, fontSize: 12 }}
              tickLine={false} axisLine={{ stroke: C.grid }} interval="preserveStartEnd" minTickGap={28} />
            <YAxis tickFormatter={shortInr} tick={{ fill: C.muted, fontSize: 12 }} tickLine={false}
              axisLine={false} width={48} />
            <Tooltip content={<Tip memory={memory} hasWhatIf={hasWhatIf} />} cursor={{ stroke: C.muted, strokeDasharray: "3 3" }} />
            <ReferenceLine y={0} stroke={C.short} strokeOpacity={0.7} strokeDasharray="4 4" />
            {key_bill && (
              <ReferenceLine x={target_date} stroke={C.ink} strokeOpacity={0.3}
                label={{ value: `${key_bill.supplier.split(" ")[0]} due`, position: "top", fill: C.ink, fontSize: 12 }} />
            )}
            {memory && (
              <Area dataKey="range" stroke="none" fill="url(#band)" type="stepAfter"
                isAnimationActive animationDuration={800} />
            )}
            <Line dataKey="naive" type="stepAfter" dot={false}
              stroke={memory ? C.muted : C.ink} strokeWidth={memory ? 1.5 : 2.5}
              strokeDasharray={memory ? "5 5" : undefined} filter={memory ? undefined : "url(#glow)"}
              isAnimationActive={false} />
            {memory && (
              <Line dataKey="likely" type="stepAfter" dot={false} stroke={C.ink} strokeWidth={2.5}
                filter="url(#glow)" animationDuration={800} />
            )}
            {hasWhatIf && (
              <Line dataKey="whatif" type="stepAfter" dot={false} stroke={C.whatif} strokeWidth={2.5}
                filter="url(#glow)" animationDuration={500} />
            )}
            {low.lowest < 0 && (
              <ReferenceDot x={low.lowest_date} y={low.lowest} r={6} fill={C.short} stroke={C.dot} strokeWidth={3} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="legend">
        {memory ? (
          <>
            <li><i className="key key-line" />Likely, from how each customer really pays</li>
            <li><i className="key key-band" />Best to worst case</li>
            {hasWhatIf && <li><i className="key key-whatif" />Your what-if</li>}
            <li><i className="key key-dash" />If everyone paid on the due date</li>
          </>
        ) : (
          <li><i className="key key-line" />Every invoice paid on its due date</li>
        )}
      </ul>
    </div>
  );
}
