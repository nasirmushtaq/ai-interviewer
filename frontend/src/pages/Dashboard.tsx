import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";
import ReportCard from "../components/ReportCard";

export default function Dashboard() {
  const { username } = useUser();
  const nav = useNavigate();
  const [data, setData] = useState<any>(null);
  const [openReport, setOpenReport] = useState<any>(null);

  useEffect(() => {
    if (!username) {
      nav("/");
      return;
    }
    api.history(username).then(setData).catch(() => {});
  }, [username]);

  if (!data) return <p>Loading…</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Your progress</h1>

      {/* Memories */}
      <section>
        <h2 className="text-lg font-semibold mb-2">🧠 What your AI friends remember</h2>
        {data.memories.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No memories yet — have a call and they'll start remembering you.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {data.memories.map((m: any) => (
              <span
                key={m.id}
                className="px-3 py-1 rounded-full bg-white/10 text-sm border border-white/10"
              >
                {m.persona_id ? `${m.persona_id}: ` : ""}
                {m.fact}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Interview reports */}
      <section>
        <h2 className="text-lg font-semibold mb-2">📊 Interview reports</h2>
        {openReport && (
          <div className="mb-4">
            <ReportCard report={openReport} />
            <button
              onClick={() => setOpenReport(null)}
              className="mt-2 text-sm text-gray-400"
            >
              Close
            </button>
          </div>
        )}
        {data.reports.length === 0 ? (
          <p className="text-gray-500 text-sm">No interviews taken yet.</p>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {data.reports.map((r: any) => (
              <button
                key={r.id}
                onClick={() => setOpenReport(r)}
                className="text-left rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 p-4"
              >
                <div className="flex justify-between">
                  <span className="font-medium">
                    {r.company ? `${r.company} · ` : ""}
                    {r.role} · {r.focus}
                  </span>
                  <span className="font-bold text-brand-400">
                    {r.overall_score}/100
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {new Date(r.created_at).toLocaleString()} · {r.difficulty}
                  {r.hints_used > 0 ? ` · ${r.hints_used} hint(s)` : ""}
                </div>
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    nav(`/replay/${r.id}`);
                  }}
                  className="mt-2 inline-block text-xs text-brand-400 hover:underline"
                >
                  ▶ Watch recording
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Conversations */}
      <section>
        <h2 className="text-lg font-semibold mb-2">💬 Past conversations</h2>
        {data.conversations.length === 0 ? (
          <p className="text-gray-500 text-sm">Nothing yet.</p>
        ) : (
          <div className="space-y-2">
            {data.conversations.map((c: any) => (
              <div
                key={c.id}
                className="rounded-xl bg-white/5 border border-white/10 p-4"
              >
                <div className="flex justify-between">
                  <span className="font-medium">{c.title}</span>
                  <span className="text-xs text-gray-500 uppercase">{c.mode}</span>
                </div>
                {c.summary && (
                  <p className="text-sm text-gray-400 mt-1">{c.summary}</p>
                )}
                <div className="text-xs text-gray-600 mt-1">
                  {new Date(c.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
