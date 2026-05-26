import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface Decision {
  id: string;
  initiative_id: string;
  title: string;
  rationale: string;
  decided_at: string;
  still_valid: boolean | null;
  last_validated_at: string | null;
}

function ValidityBadge({ valid }: { valid: boolean | null }) {
  if (valid === null)
    return (
      <span className="text-xs text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">
        not yet re-evaluated
      </span>
    );
  if (valid)
    return (
      <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
        still valid
      </span>
    );
  return (
    <span className="text-xs text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded">
      at risk
    </span>
  );
}

export default function DecisionsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["decisions"],
    queryFn: () => api<Decision[]>("/api/see/decisions"),
  });

  return (
    <div>
      <PageHeader
        title="Decisions"
        subtitle="Choices made along the way, with rationale. Periodically re-evaluated."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && <p className="text-red-700">{(error as Error).message}</p>}

      <ul className="space-y-3">
        {data?.map((d) => (
          <li
            key={d.id}
            className="bg-white border border-slate-200 rounded-lg p-4"
          >
            <div className="flex items-center gap-2">
              <h3 className="font-medium">{d.title}</h3>
              <ValidityBadge valid={d.still_valid} />
            </div>
            <p className="text-sm text-slate-600 mt-1">{d.rationale}</p>
            <p className="text-xs text-slate-400 mt-2">
              decided {new Date(d.decided_at).toLocaleDateString()}
              {d.last_validated_at &&
                ` · last validated ${new Date(d.last_validated_at).toLocaleDateString()}`}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
