import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../../lib/auth";
import { cognitoConfigured } from "../../lib/config";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const configured = cognitoConfigured();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="max-w-sm w-full bg-white border border-slate-200 rounded-lg shadow-sm p-6">
        <h1 className="text-xl font-semibold">Company Brain</h1>
        <p className="text-sm text-slate-500 mt-1">Phase 0 sign-in</p>

        {!configured && (
          <div className="mt-4 p-3 rounded border border-amber-200 bg-amber-50 text-xs text-amber-800">
            Cognito is not configured (no user pool / client id baked into this
            build). Re-run <code className="font-mono">frontend-deploy.yml</code>{" "}
            against the current ephemeral stack.
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">
              Username
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={!configured}
              className="w-full px-3 py-2 border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-slate-900 disabled:bg-slate-50 disabled:text-slate-400"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">
              Password
            </label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={!configured}
              className="w-full px-3 py-2 border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-slate-900 disabled:bg-slate-50 disabled:text-slate-400"
            />
          </div>

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !configured}
            className="w-full bg-slate-900 text-white py-2 rounded hover:bg-slate-800 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-xs text-slate-500">
          Phase 0 endpoints are also reachable without login (will be tightened
          in the next pass). Sign-in just sets your identity for audit logging.
        </p>
      </div>
    </div>
  );
}
