type Props = { label: string; value: string; sub?: string; positive?: boolean };

export default function Metric({ label, value, sub, positive }: Props) {
  return (
    <div className="bg-card border border-border rounded-2xl p-5">
      <div className="text-xs text-txt2 font-semibold uppercase tracking-widest mb-2">{label}</div>
      <div className={`text-2xl font-extrabold ${positive === true ? "text-pos" : positive === false ? "text-neg" : "text-txt"}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-txt2 mt-1">{sub}</div>}
    </div>
  );
}
