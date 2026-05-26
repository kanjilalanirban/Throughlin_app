import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { getCurrentUsername, logout } from "../lib/auth";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/initiatives", label: "Initiatives" },
  { to: "/people", label: "People" },
  { to: "/decisions", label: "Decisions" },
  { to: "/signals", label: "Signals" },
  { to: "/ask", label: "Ask" },
  { to: "/brief", label: "Brief" },
  { to: "/admin", label: "Admin" },
];

export default function Layout() {
  const navigate = useNavigate();
  const username = getCurrentUsername();

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-200">
          <div className="text-base font-semibold leading-tight">Company Brain</div>
          <div className="text-xs text-slate-500 mt-0.5">Phase 0 — internal alpha</div>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `block px-3 py-1.5 rounded text-sm ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-slate-200 text-xs">
          {username ? (
            <div className="flex items-center justify-between">
              <span className="text-slate-600 truncate" title={username}>
                {username}
              </span>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="text-slate-500 hover:text-slate-900"
              >
                Sign out
              </button>
            </div>
          ) : (
            <NavLink to="/login" className="text-slate-500 hover:text-slate-900">
              Sign in
            </NavLink>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
