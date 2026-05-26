import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface Signal {
  id: string;
  source: string;
  source_entity_id: string;
  signal_type: string;
  payload: Record<string, unknown>;
  observed_at: string;
  links_to_initiative_id: string | null;
}

function sourceColor(source: string): string {
  return (
    {
      jira: "bg-blue-50 text-blue-700 border-blue-200",
      github: "bg-slate-100 text-slate-800 border-slate-300",
      hris: "bg-purple-50 text-purple-700 border-purple-200",
    }[source] ?? "bg-slate-100 text-slate-700 border-slate-200"
  );
}

function summarize(s: Signal): string {
  const p = s.payload;
  return (
    (p.title as string) ||
    (p.summary as string) ||
    (p.message as string) ||
    s.source_entity_id
  );
}

export default function SignalsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["signals"],
    queryFn: () => api<Signal[]>("/api/see/signals?limit=200"),
  });

  return (
    <div>
      <PageHeader
        title="Signals"
        subtitle="Continuous evidence from Jira, GitHub, HRIS. How the brain tells the truth."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && <p className="text-red-700">{(error as Error).message}</p>}

      {data && data.length === 0 && (
        <p className="text-slate-500">
          No signals yet. Wire up an integration in{" "}
          <a href="/admin" className="underline">Admin</a>.
        </p>
      )}

      <ul className="space-y-2">
        {data?.map((s) => (
          <li
            key={s.id}
            className="bg-white border border-slate-200 rounded p-3 flex items-start gap-3"
          >
            <span
              className={`text-xs px-1.5 py-0.5 rounded border font-mono shrink-0 ${sourceColor(
                s.source,
              )}`}
            >
              {s.source}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm truncate">{summarize(s)}</div>
              <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                <span>{s.signal_type}</span>
                <span>·</span>
                <span className="font-mono">{s.source_entity_id}</span>
                <span>·</span>
                <span>{new Date(s.observed_at).toLocaleString()}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
