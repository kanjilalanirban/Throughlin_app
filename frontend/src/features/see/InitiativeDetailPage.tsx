import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";
import StatusPill from "../../components/StatusPill";

interface DecisionOut {
  id: string;
  title: string;
  rationale: string;
  decided_at: string;
  still_valid: boolean | null;
}

interface PersonLink {
  person_id: string;
  person_name: string;
  role_in_initiative: string | null;
  ownership_strength: number | null;
  knowledge_concentration_score: number | null;
}

interface InitiativeDetail {
  id: string;
  name: string;
  description: string | null;
  status: string;
  owner_id: string | null;
  confidence_score: number | null;
  confirmed_by_user_at: string | null;
  updated_at: string;
  inferred_from: Array<{ source: string; weight: number; reason: string }>;
  decisions: DecisionOut[];
  people: PersonLink[];
}

export default function InitiativeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["initiative", id],
    queryFn: () => api<InitiativeDetail>(`/api/see/initiatives/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-slate-500">Loading…</p>;
  if (isError) return <p className="text-red-700">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <Link to="/initiatives" className="text-sm text-slate-500 hover:text-slate-900">
        ← Initiatives
      </Link>

      <PageHeader
        title={data.name}
        subtitle={data.description ?? undefined}
        right={<StatusPill status={data.status} />}
      />

      <section className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500 mb-3">
            People
          </h3>
          {data.people.length === 0 ? (
            <p className="text-sm text-slate-500">No people linked.</p>
          ) : (
            <ul className="space-y-2">
              {data.people.map((p) => (
                <li key={p.person_id} className="flex items-baseline justify-between text-sm">
                  <span>
                    <Link
                      to={`/people/${p.person_id}`}
                      className="hover:underline font-medium"
                    >
                      {p.person_name}
                    </Link>
                    {p.role_in_initiative && (
                      <span className="text-slate-500"> · {p.role_in_initiative}</span>
                    )}
                  </span>
                  {p.ownership_strength != null && (
                    <span className="text-xs text-slate-500 tabular-nums">
                      {(Number(p.ownership_strength) * 100).toFixed(0)}%
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500 mb-3">
            Decisions
          </h3>
          {data.decisions.length === 0 ? (
            <p className="text-sm text-slate-500">No decisions recorded yet.</p>
          ) : (
            <ul className="space-y-3">
              {data.decisions.map((d) => (
                <li key={d.id}>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{d.title}</span>
                    {d.still_valid === false && (
                      <span className="text-xs text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded">
                        at risk
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-600 mt-0.5">{d.rationale}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {new Date(d.decided_at).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {data.inferred_from.length > 0 && (
        <section className="mt-6 bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-500 mb-3">
            Why this looks like an initiative
          </h3>
          <ul className="space-y-1 text-sm">
            {data.inferred_from.map((e, idx) => (
              <li key={idx}>
                <span className="font-mono text-xs text-slate-500">[{e.source}]</span>{" "}
                {e.reason}{" "}
                <span className="text-xs text-slate-400">
                  (weight {(e.weight * 100).toFixed(0)}%)
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
