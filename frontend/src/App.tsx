import { useQuery } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface HealthResponse {
  status: string;
  environment: string;
  region: string;
}

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export default function App() {
  const { data, error, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-6">
      <div className="max-w-xl w-full bg-white rounded-lg shadow-sm border border-slate-200 p-8 space-y-6">
        <header>
          <h1 className="text-2xl font-semibold">Company Brain</h1>
          <p className="text-sm text-slate-500 mt-1">Phase 0 — internal alpha</p>
        </header>

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
              Backend health
            </h2>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="text-xs px-3 py-1 rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-50"
            >
              {isFetching ? "Checking…" : "Refresh"}
            </button>
          </div>

          {isLoading && <p className="text-slate-500">Loading…</p>}

          {isError && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div className="font-medium">Could not reach backend</div>
              <div className="mt-1 font-mono text-xs">{(error as Error).message}</div>
              <div className="mt-2 text-xs text-red-600">
                API URL: <span className="font-mono">{API_URL}</span>
              </div>
            </div>
          )}

          {data && (
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <dt className="text-slate-500">Status</dt>
              <dd className="col-span-2 font-mono">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  {data.status}
                </span>
              </dd>
              <dt className="text-slate-500">Environment</dt>
              <dd className="col-span-2 font-mono">{data.environment}</dd>
              <dt className="text-slate-500">Region</dt>
              <dd className="col-span-2 font-mono">{data.region}</dd>
              <dt className="text-slate-500">API URL</dt>
              <dd className="col-span-2 font-mono text-xs break-all text-slate-600">{API_URL}</dd>
            </dl>
          )}
        </section>

        <footer className="pt-4 border-t border-slate-100 text-xs text-slate-400">
          Ephemeral stack. Tear down with <code className="font-mono">make down</code> when idle.
        </footer>
      </div>
    </div>
  );
}
