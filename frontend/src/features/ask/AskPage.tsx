import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface AskResponse {
  answer: string;
  citations: Array<{ kind: string; id: string; name: string }>;
  model: string;
  latency_ms: number;
  placeholder: boolean;
}

interface Turn {
  query: string;
  response?: AskResponse;
  error?: string;
}

export default function AskPage() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<Turn[]>([]);

  const mut = useMutation({
    mutationFn: (q: string) =>
      api<AskResponse>("/api/ask", { method: "POST", body: { query: q } }),
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    const q = query.trim();
    setQuery("");
    const turn: Turn = { query: q };
    setHistory((h) => [...h, turn]);
    try {
      const response = await mut.mutateAsync(q);
      setHistory((h) =>
        h.map((t, i) => (i === h.length - 1 ? { ...t, response } : t)),
      );
    } catch (err) {
      setHistory((h) =>
        h.map((t, i) =>
          i === h.length - 1 ? { ...t, error: (err as Error).message } : t,
        ),
      );
    }
  }

  return (
    <div>
      <PageHeader
        title="Ask"
        subtitle="Free-form questions over your initiatives, people, decisions, and signals."
      />

      <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-800 mb-4">
        Placeholder — current responses are simple name/description matches
        on initiatives. Real LLM + retrieval lands in the next milestone.
      </div>

      <div className="space-y-4 mb-6">
        {history.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="bg-slate-900 text-white rounded-lg p-3 text-sm max-w-2xl ml-auto">
              {t.query}
            </div>
            {t.error && (
              <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700 max-w-2xl">
                {t.error}
              </div>
            )}
            {t.response && (
              <div className="bg-white border border-slate-200 rounded-lg p-4 max-w-2xl text-sm">
                <p className="whitespace-pre-wrap">{t.response.answer}</p>
                {t.response.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
                      Citations
                    </div>
                    <ul className="text-sm space-y-1">
                      {t.response.citations.map((c) => (
                        <li key={c.id}>
                          <Link
                            to={`/${c.kind}s/${c.id}`}
                            className="text-slate-700 hover:underline"
                          >
                            {c.name}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="text-xs text-slate-400 mt-2">
                  {t.response.model} · {t.response.latency_ms}ms
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="flex items-center gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. payments"
          className="flex-1 px-3 py-2 border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-slate-900"
        />
        <button
          type="submit"
          disabled={mut.isPending || !query.trim()}
          className="px-4 py-2 bg-slate-900 text-white rounded hover:bg-slate-800 disabled:opacity-50"
        >
          {mut.isPending ? "Asking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
