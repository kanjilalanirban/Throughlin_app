import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface BriefResponse {
  generated_at: string;
  period_start: string;
  period_end: string;
  markdown: string;
  placeholder: boolean;
}

// Tiny markdown renderer — full markdown lib is overkill for the
// placeholder's heading/paragraph/list shape. Replace with `marked` or
// `react-markdown` when the LLM output gets richer.
function renderMd(md: string): React.ReactNode {
  const lines = md.split("\n");
  const out: React.ReactNode[] = [];
  let listBuf: string[] = [];

  function flushList() {
    if (!listBuf.length) return;
    out.push(
      <ul key={`l${out.length}`} className="list-disc pl-6 my-2 space-y-1">
        {listBuf.map((li, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: inline(li) }} />
        ))}
      </ul>,
    );
    listBuf = [];
  }

  function inline(s: string): string {
    return s
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/_(.+?)_/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, '<code class="font-mono text-xs">$1</code>');
  }

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith("- ")) {
      listBuf.push(line.slice(2));
      continue;
    }
    flushList();
    if (line.startsWith("# ")) {
      out.push(<h2 key={out.length} className="text-xl font-semibold mt-4">{line.slice(2)}</h2>);
    } else if (line.startsWith("## ")) {
      out.push(<h3 key={out.length} className="text-base font-semibold mt-4 text-slate-700">{line.slice(3)}</h3>);
    } else if (line.trim() === "") {
      out.push(<div key={out.length} className="h-2" />);
    } else if (line.startsWith("---")) {
      out.push(<hr key={out.length} className="my-4 border-slate-200" />);
    } else {
      out.push(<p key={out.length} className="text-sm" dangerouslySetInnerHTML={{ __html: inline(line) }} />);
    }
  }
  flushList();
  return out;
}

export default function BriefPage() {
  const [period, setPeriod] = useState<"last_week" | "last_month">("last_week");
  const [brief, setBrief] = useState<BriefResponse | null>(null);

  const mut = useMutation({
    mutationFn: (p: "last_week" | "last_month") =>
      api<BriefResponse>("/api/brief", { method: "POST", body: { period: p } }),
    onSuccess: setBrief,
  });

  return (
    <div>
      <PageHeader
        title="Brief"
        subtitle="Executive briefing assembled from the four primitives over a chosen window."
        right={
          <div className="flex items-center gap-2">
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value as "last_week" | "last_month")}
              className="px-3 py-1.5 border border-slate-300 rounded text-sm"
            >
              <option value="last_week">Last week</option>
              <option value="last_month">Last month</option>
            </select>
            <button
              onClick={() => mut.mutate(period)}
              disabled={mut.isPending}
              className="px-4 py-1.5 bg-slate-900 text-white text-sm rounded hover:bg-slate-800 disabled:opacity-50"
            >
              {mut.isPending ? "Generating…" : "Generate"}
            </button>
          </div>
        }
      />

      <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-800 mb-4">
        Placeholder — current brief is synthesized from DB counts, not LLM-written.
      </div>

      {mut.isError && (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(mut.error as Error).message}
        </div>
      )}

      {brief && (
        <article className="bg-white border border-slate-200 rounded-lg p-6 prose max-w-none">
          {renderMd(brief.markdown)}
        </article>
      )}

      {!brief && !mut.isPending && (
        <p className="text-slate-500 text-sm">
          Click <strong>Generate</strong> to produce a brief.
        </p>
      )}
    </div>
  );
}
