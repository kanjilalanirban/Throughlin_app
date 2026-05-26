import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import PageHeader from "../../components/PageHeader";
import StatusPill from "../../components/StatusPill";

interface Person {
  id: string;
  name: string;
  email: string;
  role: string | null;
  team: string | null;
  status: string;
  github_handle: string | null;
  jira_account_id: string | null;
}

export default function PeoplePage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["people"],
    queryFn: () => api<Person[]>("/api/see/people"),
  });

  return (
    <div>
      <PageHeader
        title="People"
        subtitle="Who actually holds the knowledge. Where concentration risk sits."
      />

      {isLoading && <p className="text-slate-500">Loading…</p>}
      {isError && <p className="text-red-700">{(error as Error).message}</p>}

      {data && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Role</th>
                <th className="text-left px-4 py-2 font-medium">Team</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Email</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-medium">{p.name}</td>
                  <td className="px-4 py-2 text-slate-600">{p.role ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{p.team ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusPill status={p.status} />
                  </td>
                  <td className="px-4 py-2 text-slate-500 font-mono text-xs">
                    {p.email}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
