import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const focusLabel = (id: string) =>
  (id || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/**
 * Post-interview coaching: model answers for the weakest questions, concepts to
 * study, and a recommended next drill. Generated on demand (one LLM call).
 */
export default function CoachingCard({
  report,
  transcript,
  sessionId,
  onDrill,
}: {
  report: any;
  transcript: any[];
  sessionId?: string | null;
  onDrill?: (focus: string, difficulty: string) => void;
}) {
  const nav = useNavigate();
  const [loading, setLoading] = useState(false);
  const [coaching, setCoaching] = useState<any>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.coaching({
        role: report.role,
        track: report.track,
        focus: report.focus,
        difficulty: report.difficulty,
        transcript,
        report,
        session_id: sessionId || undefined,
      });
      setCoaching(res);
    } catch (e: any) {
      setError(e.message || "Could not generate coaching.");
    } finally {
      setLoading(false);
    }
  };

  if (!coaching) {
    return (
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">📚 Get coaching on this interview</h3>
            <p className="text-sm text-gray-400">
              See how a strong candidate would answer your weakest questions, what
              to study next, and your recommended next drill.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="shrink-0 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-sm disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Coach me"}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-5 space-y-5">
      <h3 className="text-xl font-semibold">📚 Your coaching</h3>

      {/* Model answers */}
      {coaching.model_answers?.length > 0 && (
        <div>
          <div className="text-xs uppercase text-gray-400 mb-2">
            How a strong candidate would answer
          </div>
          <div className="space-y-3">
            {coaching.model_answers.map((m: any, i: number) => (
              <div
                key={i}
                className="rounded-xl bg-black/30 border border-white/10 p-3"
              >
                <div className="font-medium text-sm">{m.question}</div>
                {m.what_you_missed && (
                  <div className="mt-1 text-xs text-yellow-300">
                    What you missed: {m.what_you_missed}
                  </div>
                )}
                <div className="mt-2 text-sm text-gray-200 whitespace-pre-wrap">
                  {m.strong_answer}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Concepts to study */}
      {coaching.key_concepts?.length > 0 && (
        <div>
          <div className="text-xs uppercase text-gray-400 mb-2">Study these</div>
          <div className="flex flex-wrap gap-2">
            {coaching.key_concepts.map((c: string, i: number) => (
              <span
                key={i}
                className="px-2.5 py-1 rounded-full bg-white/10 border border-white/10 text-xs"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Action plan */}
      {coaching.action_plan?.length > 0 && (
        <div>
          <div className="text-xs uppercase text-gray-400 mb-2">Action plan</div>
          <ul className="list-disc list-inside text-sm text-gray-200 space-y-1">
            {coaching.action_plan.map((a: string, i: number) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Next drill */}
      {coaching.next_drill && (
        <div className="rounded-xl bg-brand-600/15 border border-brand-500/30 p-4">
          <div className="text-sm font-medium">
            🎯 Recommended next drill:{" "}
            {focusLabel(coaching.next_drill.focus)} ·{" "}
            {coaching.next_drill.difficulty}
          </div>
          {coaching.next_drill.reason && (
            <div className="text-xs text-gray-300 mt-1">
              {coaching.next_drill.reason}
            </div>
          )}
          <button
            onClick={() => {
              if (onDrill) onDrill(coaching.next_drill.focus, coaching.next_drill.difficulty);
              else nav("/interview");
            }}
            className="mt-3 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-sm"
          >
            Start this drill →
          </button>
        </div>
      )}
    </div>
  );
}
