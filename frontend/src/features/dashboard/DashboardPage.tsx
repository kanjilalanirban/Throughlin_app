import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface Stats {
  initiatives_total: number;
  initiatives_active: number;
  initiatives_proposed: number;
  people_total: number;
  people_active: number;
  decisions_total: number;
  decisions_still_valid: number;
  decisions_invalid: number;
  signals_total: number;
  signals_last_24h: number;
}

function Card({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Stats>("/api/see/dashboard"),
  });

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="High-level state of the four primitives in the seeded org."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(error as Error).message}
        </div>
      )}

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card
            label="Initiatives"
            value={data.initiatives_total}
            sub={`${data.initiatives_active} active · ${data.initiatives_proposed} proposed`}
          />
          <Card
            label="People"
            value={data.people_total}
            sub={`${data.people_active} active`}
          />
          <Card
            label="Decisions"
            value={data.decisions_total}
            sub={`${data.decisions_still_valid} valid · ${data.decisions_invalid} at risk`}
          />
          <Card
            label="Signals"
            value={data.signals_total}
            sub={`${data.signals_last_24h} in last 24h`}
          />
        </div>
      )}
    </div>
  );
}
