import { NavLink, useNavigate } from "react-router-dom";
import { ReactNode } from "react";
import { useUser } from "./user";

const linkCls = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-lg text-sm font-medium transition ${
    isActive ? "bg-brand-600 text-white" : "text-gray-300 hover:bg-white/10"
  }`;

export default function Layout({ children }: { children: ReactNode }) {
  const { username, email, authed, logout } = useUser();
  const nav = useNavigate();
  return (
    <div className="min-h-screen">
      <header className="border-b border-white/10 backdrop-blur sticky top-0 z-10 bg-[#0b1020]/80">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div
            className="font-bold text-lg cursor-pointer select-none"
            onClick={() => nav("/")}
          >
            🗣️ Lingua<span className="text-brand-400">Call</span>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink to="/" className={linkCls} end>
              Home
            </NavLink>
            <NavLink to="/interview" className={linkCls}>
              Interview
            </NavLink>
            <NavLink to="/learn" className={linkCls}>
              Learn
            </NavLink>
            <NavLink to="/progress" className={linkCls}>
              Progress
            </NavLink>
            <NavLink to="/leaderboard" className={linkCls}>
              Leaderboard
            </NavLink>
            <NavLink to="/dashboard" className={linkCls}>
              Dashboard
            </NavLink>
            {username ? (
              <button
                onClick={() => {
                  logout();
                  nav("/");
                }}
                className="ml-2 text-xs text-gray-400 hover:text-white"
                title={authed ? email || "" : "guest"}
              >
                {username}
                {authed ? "" : " (guest)"} · logout
              </button>
            ) : null}
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
    </div>
  );
}
