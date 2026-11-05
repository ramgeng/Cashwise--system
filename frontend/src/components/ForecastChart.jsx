import {
  Area, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { day, inr, shortInr } from "../format.js";

const C = { ink: "#16263D", band: "#1F7A6D", short: "#B4292B", muted: "#8A93A0", grid: "#D9DFDA" };

function Tip({ active, payload, label, memory }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{day(label)}</strong>
      {memory ? (
        <>
          <span>Likely {inr(d.likely)}</span>
          <span className="muted">Best {inr(d.best)}, worst {inr(d.worst)}</span>
          <span className="muted">Due-date view {inr(d.naive)}</span>
        </>
      ) : (
        <span>Balance {inr(d.naive)}</span>
      )}
    </div>
  );
}

export default function ForecastChart({ data, memory }) {
  const { days, target_date, key_bill, summary } = data;
  const rows = days.map((d) => ({ ...d, range: [d.worst, d.best] }));
  const low = memory ? summary.likely : summary.naive;

  return (
    <div className="chart" role="img"
      aria-label={`Cash forecast. Lowest ${memory ? "likely " : ""}balance ${inr(low.lowest)} on ${day(low.lowest_date)}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 24, right: 12, bottom: 0, left: 4 }}>
          <XAxis dataKey="date" tickFormatter={day} tick={{ fill: C.muted, fontSize: 12 }}
            tickLine={false} axisLine={{ stroke: C.grid }} interval="preserveStartEnd" minTickGap={28} />
          <YAxis tickFormatter={shortInr} tick={{ fill: C.muted, fontSize: 12 }} tickLine={false}
            axisLine={false} width={48} />
          <Tooltip content={<Tip memory={memory} />} />
          <ReferenceLine y={0} stroke={C.short} strokeDasharray="4 4" />
          {key_bill && (
            <ReferenceLine x={target_date} stroke={C.ink} strokeOpacity={0.35}
              label={{ value: `${key_bill.supplier.split(" ")[0]} due`, position: "top", fill: C.ink, fontSize: 12 }} />
          )}
          {memory && (
            <Area dataKey="range" stroke="none" fill={C.band} fillOpacity={0.18} type="stepAfter"
              isAnimationActive animationDuration={700} />
          )}
          <Line dataKey="naive" type="stepAfter" dot={false}
            stroke={memory ? C.muted : C.ink} strokeWidth={memory ? 1.5 : 2.5}
            strokeDasharray={memory ? "5 5" : undefined} isAnimationActive={false} />
          {memory && (
            <Line dataKey="likely" type="stepAfter" dot={false} stroke={C.ink} strokeWidth={2.5}
              animationDuration={700} />
          )}
          {low.lowest < 0 && (
            <ReferenceDot x={low.lowest_date} y={low.lowest} r={5} fill={C.short} stroke="#fff" strokeWidth={2} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <ul className="legend">
        {memory ? (
          <>
            <li><i className="key key-line" />Likely, from how each customer actually pays</li>
            <li><i className="key key-band" />Best to worst case</li>
            <li><i className="key key-dash" />If everyone paid on the due date</li>
          </>
        ) : (
          <li><i className="key key-line" />Every invoice paid on its due date</li>
        )}
      </ul>
    </div>
  );
}
