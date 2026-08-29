import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";

const focusLabel = (id: string) =>
  (id || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function Learn() {
  const nav = useNavigate();
  const { authed } = useUser();
  const [packs, setPacks] = useState<any[]>([]);
  const [paths, setPaths] = useState<any[]>([]);
  const [review, setReview] = useState<any>(null);

  useEffect(() => {
    api.companyPacks().then(setPacks).catch(() => {});
    api.learningPaths().then(setPaths).catch(() => {});
    if (authed) api.reviewQueue().then(setReview).catch(() => {});
  }, [authed]);

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Prep & Learn 🎓</h1>

      {/* Spaced-repetition review */}
      {authed && review?.due?.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-2">🔁 Due for review</h2>
          <p className="text-sm text-gray-400 mb-3">
            Concepts you struggled with before — revisit them in your next session.
          </p>
          <div className="flex flex-wrap gap-2">
            {review.due.map((d: any, i: number) => (
              <span
                key={i}
                title={`from ${d.from_focus}, ${d.last_seen_days}d ago`}
                className="px-3 py-1.5 rounded-full bg-yellow-500/15 border border-yellow-500/30 text-yellow-200 text-sm"
              >
                {d.concept}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Learning paths */}
      <section>
        <h2 className="text-lg font-semibold mb-3">📚 Learning paths</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {paths.map((p) => (
            <div
              key={p.id}
              className="rounded-2xl bg-white/5 border border-white/10 p-5"
            >
              <div className="font-semibold text-lg">{p.name}</div>
              <div className="text-sm text-gray-400">{p.blurb}</div>
              <div className="mt-3 h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-brand-500"
                  style={{ width: `${(p.completed / p.total) * 100}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {p.completed}/{p.total} steps done
              </div>
              <div className="mt-3 space-y-1">
                {p.steps.map((s: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className={s.done ? "text-green-300" : "text-gray-300"}>
                      {s.done ? "✓" : "○"} {s.title}
                    </span>
                    <button
                      onClick={() => nav("/interview")}
                      className="text-xs text-brand-400 hover:underline"
                    >
                      {focusLabel(s.focus)} · {s.difficulty} →
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Company packs */}
      <section>
        <h2 className="text-lg font-semibold mb-3">🏢 Company prep packs</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          {packs.map((p) => (
            <div
              key={p.id}
              className="rounded-2xl bg-white/5 border border-white/10 p-5"
            >
              <div className="font-semibold text-lg">{p.name}</div>
              <div className="text-sm text-gray-400">{p.blurb}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {p.sessions.map((s: any, i: number) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full bg-white/10 text-xs"
                  >
                    {focusLabel(s.focus)} · {s.difficulty}
                  </span>
                ))}
              </div>
              <button
                onClick={() => nav("/interview")}
                className="mt-3 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-sm"
              >
                Start this pack →
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
