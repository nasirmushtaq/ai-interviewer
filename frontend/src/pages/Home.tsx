import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";
import AuthPanel from "../components/AuthPanel";

type Persona = {
  id: string;
  name: string;
  tagline: string;
  avatar: string;
};

export default function Home() {
  const { username, ready } = useUser();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    api.personas().then(setPersonas).catch(() => {});
    api.health().then((h) => setHasKey(h.has_openai_key)).catch(() => setHasKey(false));
  }, []);

  // Avoid a flash of the auth screen while we restore a saved session.
  if (!ready) {
    return <div className="mt-16 text-center text-gray-500">Loading…</div>;
  }

  if (!username) {
    return <AuthPanel />;
  }

  return (
    <div>
      {hasKey === false && (
        <div className="mb-6 rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-200">
          ⚠️ No OpenAI API key configured on the server. Add one to{" "}
          <code>backend/.env</code> to enable live voice calls, memory and grading.
        </div>
      )}
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Hey {username} 👋</h1>
          <p className="text-gray-400">
            {personas.length > 0
              ? "Pick who you want to talk to today."
              : "Ready to sharpen your interview skills?"}
          </p>
        </div>
      </div>

      {/* Primary CTA: mock interview */}
      <div className="grid sm:grid-cols-2 gap-4 mb-4">
        <button
          onClick={() => nav("/interview")}
          className="text-left rounded-2xl bg-brand-600/20 border border-brand-500/40 hover:bg-brand-600/30 transition p-6"
        >
          <div className="text-3xl">🎯</div>
          <div className="font-semibold text-lg mt-2">Start a mock interview</div>
          <div className="text-sm text-gray-400">
            Realistic System Design interview with an AI interviewer, live
            feedback, and grading.
          </div>
          <div className="mt-3 text-xs text-brand-300">Begin →</div>
        </button>
        <button
          onClick={() => nav("/learn")}
          className="text-left rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition p-6"
        >
          <div className="text-3xl">🎓</div>
          <div className="font-semibold text-lg mt-2">Prep & learn</div>
          <div className="text-sm text-gray-400">
            Company packs, learning paths, and topics to review.
          </div>
          <div className="mt-3 text-xs text-brand-300">Explore →</div>
        </button>
      </div>

      {/* Persona calls (only when enabled) */}
      {personas.length > 0 && (
        <>
          <div className="text-sm text-gray-400 mt-6 mb-2">
            Or practice English on a call:
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {personas.map((p) => (
              <button
                key={p.id}
                onClick={() => nav(`/call/${p.id}`)}
                className="text-left rounded-2xl bg-white/5 border border-white/10 hover:border-brand-500 hover:bg-white/10 transition p-5 flex gap-4 items-center"
              >
                <div className="w-16 h-16 rounded-full bg-brand-600/30 flex items-center justify-center text-4xl">
                  {p.avatar}
                </div>
                <div>
                  <div className="font-semibold text-lg">{p.name}</div>
                  <div className="text-sm text-gray-400">{p.tagline}</div>
                  <div className="mt-2 text-xs text-brand-400">Tap to call →</div>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
