import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";

function scoreColor(n: number) {
  if (n >= 75) return "text-green-400";
  if (n >= 50) return "text-yellow-400";
  return "text-red-400";
}
function barColor(n: number) {
  if (n >= 75) return "bg-green-500";
  if (n >= 50) return "bg-yellow-500";
  return "bg-red-500";
}

function TrendChart({ trend }: { trend: any[] }) {
  if (trend.length < 2) {
    return (
      <p className="text-gray-500 text-sm">
        Take a couple more interviews to see your score trend.
      </p>
    );
  }
  const w = 640;
  const h = 180;
  const pad = 28;
  const xs = (i: number) =>
    pad + (i * (w - 2 * pad)) / (trend.length - 1);
  const ys = (v: number) => h - pad - (v / 100) * (h - 2 * pad);
  const pts = trend.map((t, i) => `${xs(i)},${ys(t.score)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      {[0, 25, 50, 75, 100].map((g) => (
        <g key={g}>
          <line
            x1={pad}
            x2={w - pad}
            y1={ys(g)}
            y2={ys(g)}
            stroke="rgba(255,255,255,0.08)"
          />
          <text x={4} y={ys(g) + 3} fill="#6b7280" fontSize="9">
            {g}
          </text>
        </g>
      ))}
      <polyline
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        points={pts}
      />
      {trend.map((t, i) => (
        <circle key={i} cx={xs(i)} cy={ys(t.score)} r="3.5" fill="#818cf8">
          <title>
            {new Date(t.date).toLocaleDateString()} · {t.focus} · {t.score}/100
          </title>
        </circle>
      ))}
    </svg>
  );
}

export default function Progress() {
  const { username, authed } = useUser();
  const nav = useNavigate();
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!username) {
      nav("/");
      return;
    }
    api
      .stats()
      .then(setStats)
      .catch((e) => setError(e.message || "Could not load progress."));
  }, [username]);

  if (!authed) {
    return (
      <div className="mt-16 text-center">
        <h1 className="text-2xl font-bold">Track your progress</h1>
        <p className="text-gray-400 mt-2">
          Log in with an account to see your score trends, weak areas and streaks.
        </p>
        <button
          onClick={() => nav("/")}
          className="mt-4 px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500"
        >
          Log in / Sign up
        </button>
      </div>
    );
  }

  if (error) return <p className="text-red-400">{error}</p>;
  if (!stats) return <p className="text-gray-400">Loading your progress…</p>;

  if (stats.total_interviews === 0) {
    return (
      <div className="mt-16 text-center">
        <h1 className="text-2xl font-bold">No interviews yet</h1>
        <p className="text-gray-400 mt-2">
          Take your first mock interview and your progress will show up here.
        </p>
        <button
          onClick={() => nav("/interview")}
          className="mt-4 px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500"
        >
          Start an interview
        </button>
      </div>
    );
  }

  const imp = stats.recent_improvement;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Your progress 📈</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <div className="text-xs text-gray-400">Interviews</div>
          <div className="text-3xl font-bold">{stats.total_interviews}</div>
        </div>
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <div className="text-xs text-gray-400">Average score</div>
          <div className={`text-3xl font-bold ${scoreColor(stats.average_score)}`}>
            {stats.average_score}
          </div>
        </div>
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <div className="text-xs text-gray-400">Best score</div>
          <div className={`text-3xl font-bold ${scoreColor(stats.best_score)}`}>
            {stats.best_score}
          </div>
        </div>
        <div className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <div className="text-xs text-gray-400">🔥 Streak</div>
          <div className="text-3xl font-bold">
            {stats.streak.current}
            <span className="text-sm text-gray-500"> day{stats.streak.current === 1 ? "" : "s"}</span>
          </div>
          <div className="text-xs text-gray-500">longest {stats.streak.longest}</div>
        </div>
      </div>

      {imp !== 0 && (
        <div
          className={`rounded-xl px-4 py-3 text-sm border ${
            imp > 0
              ? "bg-green-500/10 border-green-500/30 text-green-300"
              : "bg-yellow-500/10 border-yellow-500/30 text-yellow-300"
          }`}
        >
          {imp > 0
            ? `You're improving — up ${imp} points recently. Keep it going!`
            : `Down ${Math.abs(imp)} points recently — try a focused drill on your weak areas.`}
        </div>
      )}

      {/* Trend chart */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="text-sm font-semibold mb-3">Score over time</div>
        <TrendChart trend={stats.trend} />
      </div>

      {/* Weak-area heatmap */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="text-sm font-semibold mb-3">Skill breakdown</div>
        <div className="space-y-3">
          {stats.dimensions.map((d: any) => (
            <div key={d.id}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-300">{d.label}</span>
                <span className={scoreColor(d.average)}>{d.average}</span>
              </div>
              <div className="h-2.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className={`h-full ${barColor(d.average)}`}
                  style={{ width: `${d.average}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        {stats.weak_areas.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 items-center">
            <span className="text-xs text-gray-400">Focus next on:</span>
            {stats.weak_areas.map((w: any) => (
              <button
                key={w.id}
                onClick={() => nav("/interview")}
                className="px-3 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-red-300 text-xs hover:bg-red-500/25"
              >
                {w.label} ({w.average}) — drill →
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Per-track */}
      {stats.by_track.length > 0 && (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="text-sm font-semibold mb-3">By track</div>
          <div className="grid sm:grid-cols-2 gap-3">
            {stats.by_track.map((t: any) => (
              <div
                key={t.track}
                className="rounded-xl bg-white/5 border border-white/10 p-3 flex justify-between"
              >
                <div>
                  <div className="font-medium capitalize">{t.track.replace(/_/g, " ")}</div>
                  <div className="text-xs text-gray-500">{t.count} interviews</div>
                </div>
                <div className="text-right">
                  <div className={`font-bold ${scoreColor(t.average)}`}>{t.average}</div>
                  <div className="text-xs text-gray-500">best {t.best}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
