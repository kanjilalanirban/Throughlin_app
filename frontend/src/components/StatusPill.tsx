interface Props {
  status: string;
}

const TONE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  proposed: "bg-amber-50 text-amber-700 border-amber-200",
  on_hold: "bg-slate-100 text-slate-700 border-slate-200",
  completed: "bg-sky-50 text-sky-700 border-sky-200",
  cancelled: "bg-slate-100 text-slate-500 border-slate-200",
  departed: "bg-slate-100 text-slate-500 border-slate-200",
  on_leave: "bg-amber-50 text-amber-700 border-amber-200",
};

export default function StatusPill({ status }: Props) {
  const tone = TONE[status] ?? "bg-slate-100 text-slate-700 border-slate-200";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded border ${tone}`}>
      {status}
    </span>
  );
}
