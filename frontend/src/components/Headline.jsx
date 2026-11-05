import { inr, longDay } from "../format.js";

// The sentence the owner reads first: will I be able to pay the next big bill?
export default function Headline({ data, memory }) {
  const { key_bill, target_date, summary } = data;
  const s = memory ? summary.likely : summary.naive;
  const v = s.on_target ?? s.lowest;
  const short = v < 0;

  const lead = key_bill
    ? `After paying ${key_bill.supplier} ${inr(key_bill.amount)} on ${longDay(target_date)}`
    : `By ${longDay(target_date)}`;

  return (
    <section className="headline" aria-live="polite">
      <p className="lead">{lead}</p>
      <h1 className={short ? "is-short" : "is-ok"}>
        {memory ? "you will likely be " : "you will have "}
        <span className="figure">{short ? `${inr(-v)} short` : `${inr(v)} left`}</span>
      </h1>
      {memory ? (
        <p className="range">
          Best case {summary.best.on_target >= 0 ? `${inr(summary.best.on_target)} left` : `${inr(-summary.best.on_target)} short`}.{" "}
          Worst case {summary.worst.on_target >= 0 ? `${inr(summary.worst.on_target)} left` : `${inr(-summary.worst.on_target)} short`}.{" "}
          A due-date dashboard would show <s>{inr(summary.naive.on_target)} left</s>.
        </p>
      ) : (
        <p className="range">This view assumes every customer pays on the due date. Turn on memory to see how they really pay.</p>
      )}
    </section>
  );
}
