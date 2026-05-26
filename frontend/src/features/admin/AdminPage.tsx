import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, ApiError } from "../../lib/api";
import PageHeader from "../../components/PageHeader";

interface Integration {
  name: "jira" | "github" | "hris";
  label: string;
  configured: boolean;
  description: string;
  last_run_at: string | null;
  last_run_status: string | null;
  records_processed_last_run: number | null;
}

interface UploadResult {
  upserted: number;
  departed_flagged: number;
  errors: string[];
}

function IntegrationCard({ i }: { i: Integration }) {
  const last = i.last_run_at
    ? new Date(i.last_run_at).toLocaleString()
    : "never";
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{i.label}</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded border ${
            i.configured
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : "bg-amber-50 text-amber-700 border-amber-200"
          }`}
        >
          {i.configured ? "configured" : "not configured"}
        </span>
      </div>
      <p className="text-sm text-slate-600 mt-1">{i.description}</p>
      <p className="text-xs text-slate-400 mt-3">
        last run: {last}
        {i.last_run_status && ` · ${i.last_run_status}`}
        {i.records_processed_last_run != null &&
          ` · ${i.records_processed_last_run} records`}
      </p>
    </div>
  );
}

function HrisUploader({ onDone }: { onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<UploadResult | null>(null);

  const mut = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api<UploadResult>("/api/admin/integrations/hris/upload", {
        method: "POST",
        formData: fd,
      });
    },
    onSuccess: (r) => {
      setResult(r);
      onDone();
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const f = fileRef.current?.files?.[0];
    if (!f) return;
    mut.mutate(f);
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <h3 className="font-semibold">Upload HRIS CSV</h3>
      <p className="text-sm text-slate-600 mt-1">
        Columns required: <code className="font-mono text-xs">employee_id,
        name, email, role, team, status</code>. Optional:{" "}
        <code className="font-mono text-xs">manager_email, start_date,
        github_handle, jira_account_id</code>. Rows upsert into the people
        table; emails missing from the file are flagged as{" "}
        <code className="font-mono text-xs">departed</code>.
      </p>
      <form onSubmit={submit} className="mt-4 flex items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          required
          className="text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:border-slate-300 file:bg-slate-50 file:text-sm file:font-medium"
        />
        <button
          type="submit"
          disabled={mut.isPending}
          className="px-4 py-1.5 bg-slate-900 text-white text-sm rounded hover:bg-slate-800 disabled:opacity-50"
        >
          {mut.isPending ? "Uploading…" : "Upload"}
        </button>
      </form>

      {mut.isError && (
        <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {(mut.error as ApiError).message}
        </div>
      )}
      {result && (
        <div className="mt-3 text-sm bg-emerald-50 border border-emerald-200 rounded p-3">
          <div className="font-medium text-emerald-900">Upload complete</div>
          <div className="text-emerald-800">
            {result.upserted} upserted · {result.departed_flagged} flagged as departed
          </div>
          {result.errors.length > 0 && (
            <details className="mt-2 text-xs text-amber-800">
              <summary>
                {result.errors.length} row error{result.errors.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-1 list-disc pl-5">
                {result.errors.slice(0, 25).map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => api<{ integrations: Integration[] }>("/api/admin/integrations"),
  });

  return (
    <div>
      <PageHeader
        title="Admin"
        subtitle="Configure where Company Brain pulls signals from."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && <p className="text-red-700">{(error as Error).message}</p>}

      {data && (
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          {data.integrations.map((i) => (
            <IntegrationCard key={i.name} i={i} />
          ))}
        </div>
      )}

      <HrisUploader
        onDone={() => {
          qc.invalidateQueries({ queryKey: ["integrations"] });
          qc.invalidateQueries({ queryKey: ["people"] });
          qc.invalidateQueries({ queryKey: ["dashboard"] });
        }}
      />
    </div>
  );
}
