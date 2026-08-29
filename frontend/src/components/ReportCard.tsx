const FOCUS_LABELS: Record<string, string> = {
  problem_solving: "Problem Solving",
  technical_depth: "Technical Depth",
  communication: "Communication",
  correctness: "Correctness",
  // System-design rubric dimensions
  requirements: "Requirements",
  estimation: "Capacity Estimation",
  api_data_model: "API & Data Model",
  high_level_architecture: "High-level Architecture",
  data_flow: "Data / Request Flow",
  storage_consistency: "Storage & Consistency",
  caching_performance: "Caching & Performance",
  availability_fault_tolerance: "Availability & Fault Tolerance",
  scalability_partitioning: "Scalability & Partitioning",
  concurrency_distributed: "Concurrency & Distributed",
  security_reliability: "Security & Reliability",
  operations: "Operations",
  tradeoffs: "Trade-offs",
};

function scoreColor(n: number) {
  if (n >= 75) return "text-green-400";
  if (n >= 50) return "text-yellow-400";
  return "text-red-400";
}

export default function ReportCard({ report }: { report: any }) {
  const scores = report.scores || {};
  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold">Interview Report</h3>
        <div className="text-right">
          <div className={`text-4xl font-bold ${scoreColor(report.overall_score)}`}>
            {report.overall_score}
            <span className="text-lg text-gray-500">/100</span>
          </div>
          <div className="text-xs text-gray-400">
            {report.company ? `${report.company} · ` : ""}
            {report.role} · {report.focus} · {report.difficulty}
          </div>
          {report.hints_used > 0 && (
            <div className="text-xs text-yellow-300 mt-1">
              {report.hints_used} hint{report.hints_used > 1 ? "s" : ""} used
              {report.raw_score != null
                ? ` · ${report.raw_score} − ${report.hint_penalty} penalty`
                : ` · −${report.hint_penalty} pts`}
            </div>
          )}
        </div>
      </div>

      {Object.keys(scores).length > 0 && (
        <div className="mt-5 space-y-3">
          {Object.entries(scores).map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-300">{FOCUS_LABELS[k] || k}</span>
                <span className={scoreColor(v as number)}>{v as number}</span>
              </div>
              <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-brand-500"
                  style={{ width: `${v as number}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-5 grid sm:grid-cols-2 gap-4">
        <div>
          <div className="text-xs uppercase text-gray-400 mb-1">Strengths</div>
          <ul className="text-sm list-disc list-inside text-green-300 space-y-1">
            {(report.strengths || []).map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase text-gray-400 mb-1">To improve</div>
          <ul className="text-sm list-disc list-inside text-yellow-300 space-y-1">
            {(report.improvements || []).map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      </div>

      {Array.isArray(report.rubric) && report.rubric.length > 0 && (
        <div className="mt-5">
          <div className="text-xs uppercase text-gray-400 mb-2">
            Detailed rubric — and how a strong candidate would reason
          </div>
          <div className="space-y-3">
            {report.rubric.map((r: any, i: number) => (
              <div
                key={i}
                className="rounded-xl bg-black/30 border border-white/10 p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">
                    {r.area || FOCUS_LABELS[r.dimension] || "Area"}
                  </span>
                  {typeof r.score === "number" && (
                    <span className={`text-sm font-bold ${scoreColor(r.score)}`}>
                      {r.score}
                    </span>
                  )}
                </div>
                {r.what_happened && (
                  <div className="mt-1 text-xs text-gray-300">
                    {r.what_happened}
                  </div>
                )}
                {r.how_a_strong_candidate_reasons && (
                  <div className="mt-2 text-xs text-brand-200">
                    <span className="text-brand-400 font-medium">
                      How a strong candidate reasons:{" "}
                    </span>
                    {r.how_a_strong_candidate_reasons}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {report.feedback && (
        <div className="mt-5">
          <div className="text-xs uppercase text-gray-400 mb-1">
            Interviewer feedback
          </div>
          <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
            {report.feedback}
          </p>
        </div>
      )}
    </div>
  );
}
