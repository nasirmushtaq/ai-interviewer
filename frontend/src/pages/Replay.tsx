import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";
import ReportCard from "../components/ReportCard";

export default function Replay() {
  const { reportId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .replay(Number(reportId))
      .then(setData)
      .catch((e) => setError(e.message || "Could not load recording."));
  }, [reportId]);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!data) return <p className="text-gray-400">Loading recording…</p>;

  return (
    <div className="space-y-6">
      <button onClick={() => nav(-1)} className="text-sm text-gray-400">
        ← Back
      </button>
      <h1 className="text-2xl font-bold">Interview recording</h1>

      <ReportCard report={data.report} />

      {/* Transcript */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <div className="text-sm font-semibold mb-3">Transcript</div>
        {(!data.transcript || data.transcript.length === 0) && (
          <p className="text-gray-500 text-sm">No transcript recorded.</p>
        )}
        <div className="space-y-3">
          {data.transcript.map((t: any, i: number) => (
            <div
              key={i}
              className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm ${
                t.role === "user"
                  ? "ml-auto bg-brand-600 text-white rounded-br-sm"
                  : "bg-white/10 rounded-bl-sm"
              }`}
            >
              {t.text}
            </div>
          ))}
        </div>
      </div>

      {/* Code */}
      {data.code?.source && (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="text-sm font-semibold mb-2">
            Your code ({data.code.language})
          </div>
          <pre className="text-xs bg-black/40 rounded-lg p-3 overflow-x-auto">
            {data.code.source}
          </pre>
          {data.code.result && (
            <div className="mt-2 text-xs text-gray-400">
              Tests: examples {data.code.result.example_passed}/
              {data.code.result.example_total} · hidden{" "}
              {data.code.result.hidden_passed}/{data.code.result.hidden_total}
            </div>
          )}
        </div>
      )}

      {/* Diagram */}
      {data.diagram && (
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="text-sm font-semibold mb-2">Your whiteboard</div>
          <img
            src={data.diagram}
            alt="whiteboard"
            className="rounded-lg border border-white/10 bg-white max-w-full"
          />
        </div>
      )}
    </div>
  );
}
