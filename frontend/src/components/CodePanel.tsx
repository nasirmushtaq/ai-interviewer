import { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { api } from "../api";

type Lang = { id: string; label: string; monaco: string };
type Problem = {
  id: string;
  title: string;
  difficulty: string;
  statement: string;
  starter: Record<string, string>;
  examples: { input: string; expected: string }[];
  hidden_count: number;
};

export default function CodePanel({
  sessionId,
  onResult,
}: {
  sessionId: string;
  onResult?: (summary: any) => void;
}) {
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [language, setLanguage] = useState("python");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);
  const [submitResult, setSubmitResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.codingLanguages().then(setLanguages).catch(() => {});
    loadProblem();
  }, []);

  const loadProblem = async () => {
    setLoading(true);
    setError("");
    setRunResult(null);
    setSubmitResult(null);
    try {
      const p = await api.getProblem(sessionId, {});
      setProblem(p);
      setSource(p.starter?.[language] || "");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Swap starter code when language changes (only if user hasn't typed much).
  useEffect(() => {
    if (!problem) return;
    setSource(problem.starter?.[language] || "");
  }, [language]);

  const monacoLang = useMemo(
    () => languages.find((l) => l.id === language)?.monaco || "python",
    [languages, language]
  );

  const run = async () => {
    setRunning(true);
    setError("");
    setRunResult(null);
    try {
      const r = await api.runCode(sessionId, { language, source });
      setRunResult(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const submit = async () => {
    setRunning(true);
    setError("");
    setSubmitResult(null);
    try {
      const r = await api.submitCode(sessionId, { language, source });
      setSubmitResult(r);
      onResult?.(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-4">
      {/* Problem + tests */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-4 h-[32rem] overflow-y-auto">
        {loading && <p className="text-gray-400">Loading problem…</p>}
        {problem && (
          <>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-lg">{problem.title}</h3>
              <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 capitalize">
                {problem.difficulty}
              </span>
            </div>
            <pre className="mt-2 text-sm text-gray-300 whitespace-pre-wrap font-sans">
              {problem.statement}
            </pre>
            <div className="mt-3 text-xs uppercase text-gray-400">
              Example tests
            </div>
            {problem.examples.map((ex, i) => (
              <div key={i} className="mt-2 rounded-lg bg-black/30 border border-white/10 p-2 text-xs font-mono">
                <div className="text-gray-400">Input:</div>
                <div className="whitespace-pre-wrap">{ex.input}</div>
                <div className="text-gray-400 mt-1">Expected:</div>
                <div className="whitespace-pre-wrap">{ex.expected}</div>
              </div>
            ))}
            <div className="mt-2 text-xs text-gray-500">
              + {problem.hidden_count} hidden test
              {problem.hidden_count === 1 ? "" : "s"} (run on Submit)
            </div>
            <button
              onClick={loadProblem}
              className="mt-3 text-xs text-brand-400 hover:underline"
            >
              ↻ New problem
            </button>
          </>
        )}
      </div>

      {/* Editor + actions */}
      <div className="flex flex-col h-[32rem]">
        <div className="flex items-center gap-2 mb-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-white/10 border border-white/10 text-sm"
          >
            {languages.map((l) => (
              <option key={l.id} value={l.id} className="bg-[#0b1020]">
                {l.label}
              </option>
            ))}
          </select>
          <button
            onClick={run}
            disabled={running}
            className="px-4 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm disabled:opacity-50"
          >
            ▶ Run examples
          </button>
          <button
            onClick={submit}
            disabled={running}
            className="px-4 py-1.5 rounded-lg bg-green-600 hover:bg-green-500 text-sm disabled:opacity-50"
          >
            ✓ Submit
          </button>
        </div>

        <div className="flex-1 rounded-xl overflow-hidden border border-white/10">
          <Editor
            height="100%"
            language={monacoLang}
            theme="vs-dark"
            value={source}
            onChange={(v) => setSource(v || "")}
            options={{ minimap: { enabled: false }, fontSize: 13 }}
          />
        </div>

        {/* Results console */}
        <div className="mt-2 max-h-40 overflow-y-auto text-sm">
          {running && <p className="text-yellow-300">Executing…</p>}
          {error && <p className="text-red-400">{error}</p>}
          {runResult && (
            <div>
              <div className="text-gray-300">
                Examples: {runResult.passed}/{runResult.total} passed
              </div>
              {runResult.results?.map((r: any, i: number) => (
                <div
                  key={i}
                  className={`mt-1 text-xs font-mono ${
                    r.passed ? "text-green-300" : "text-red-300"
                  }`}
                >
                  {r.passed ? "✓" : "✗"} {r.status}
                  {!r.passed && r.stdout ? ` — got: ${r.stdout.slice(0, 60)}` : ""}
                  {!r.passed && r.stderr ? ` — ${r.stderr.slice(0, 80)}` : ""}
                </div>
              ))}
            </div>
          )}
          {submitResult && (
            <div className="text-gray-200">
              <div className="font-medium">
                Examples {submitResult.example_passed}/{submitResult.example_total} ·{" "}
                Hidden {submitResult.hidden_passed}/{submitResult.hidden_total}
              </div>
              <div
                className={
                  submitResult.passed === submitResult.total
                    ? "text-green-400"
                    : "text-yellow-400"
                }
              >
                Total {submitResult.passed}/{submitResult.total} passed
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
