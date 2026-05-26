import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";
import StatusPill from "../../components/StatusPill";

interface Initiative {
  id: string;
  name: string;
  description: string | null;
  status: string;
  owner_id: string | null;
  confidence_score: number | null;
  confirmed_by_user_at: string | null;
  updated_at: string;
}

export default function InitiativesPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["initiatives"],
    queryFn: () => api<Initiative[]>("/api/see/initiatives"),
  });

  return (
    <div>
      <PageHeader
        title="Initiatives"
        subtitle="Long-lived strategic bets. The unit of executive attention."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && <p className="text-red-700">{(error as Error).message}</p>}

      {data && data.length === 0 && (
        <p className="text-slate-500">No initiatives yet.</p>
      )}

      <div className="space-y-3">
        {data?.map((i) => (
          <Link
            key={i.id}
            to={`/initiatives/${i.id}`}
            className="block bg-white border border-slate-200 rounded-lg p-4 hover:border-slate-400"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold truncate">{i.name}</h2>
                  <StatusPill status={i.status} />
                  {i.status === "proposed" && (
                    <span className="text-xs text-slate-500">
                      confidence {(Number(i.confidence_score ?? 0) * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {i.description && (
                  <p className="text-sm text-slate-600 mt-1 line-clamp-2">{i.description}</p>
                )}
              </div>
              <div className="text-xs text-slate-400 shrink-0">
                updated {new Date(i.updated_at).toLocaleDateString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
