import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";
import { useVoiceCall } from "../hooks/useVoiceCall";
import CallStage from "../components/CallStage";
import ReportCard from "../components/ReportCard";
import CoachingCard from "../components/CoachingCard";
import CodePanel from "../components/CodePanel";
import Whiteboard from "../components/Whiteboard";
import Pricing from "../components/Pricing";

type Track = {
  id: string;
  name: string;
  emoji: string;
  focuses: { id: string; brief: string }[];
};
type Company = { id: string; name: string };
type Difficulty = { id: string; label: string; question: string };
type HintTier = { tier: number; label: string; penalty: number; reveal: string };

const focusLabel = (id: string) =>
  id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function Interview() {
  const { username } = useUser();
  const nav = useNavigate();

  // catalog
  const [tracks, setTracks] = useState<Track[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [difficulties, setDifficulties] = useState<Difficulty[]>([]);
  const [designTopics, setDesignTopics] = useState<string[]>([]);
  const [hintTiers, setHintTiers] = useState<HintTier[]>([]);

  // selection
  const [trackId, setTrackId] = useState("sde");
  const [focus, setFocus] = useState("system_design");
  const [companyId, setCompanyId] = useState("google");
  const [customCompany, setCustomCompany] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [role, setRole] = useState("");
  const [note, setNote] = useState("");
  const [hintsEnabled, setHintsEnabled] = useState(true);

  // runtime
  const [started, setStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [grading, setGrading] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [hintOpen, setHintOpen] = useState(false);
  const [lastHint, setLastHint] = useState<any>(null);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintsUsed, setHintsUsed] = useState(0);
  const [penalty, setPenalty] = useState(0);
  const [typed, setTyped] = useState("");
  const [paywall, setPaywall] = useState(false);
  const [paywallReason, setPaywallReason] = useState("");
  const [startError, setStartError] = useState("");
  const [entitlement, setEntitlement] = useState<any>(null);
  const [resumeSummary, setResumeSummary] = useState<string>("");
  const [useResume, setUseResume] = useState(false);
  const [jobDesc, setJobDesc] = useState("");
  const [resumeBusy, setResumeBusy] = useState(false);
  const { engine, browserSupported, call } = useVoiceCall();

  useEffect(() => {
    if (!username) nav("/");
    api.tracks().then(setTracks).catch(() => {});
    api.companies().then(setCompanies).catch(() => {});
    api.difficulties().then(setDifficulties).catch(() => {});
    api.designTopics().then(setDesignTopics).catch(() => {});
    api.hintTiers().then(setHintTiers).catch(() => {});
    api.entitlement().then(setEntitlement).catch(() => {});
    api
      .getResume()
      .then((r) => {
        if (r.has_resume) {
          setResumeSummary(r.summary);
          setUseResume(true);
        }
      })
      .catch(() => {});
  }, [username]);

  const uploadResume = async (file: File) => {
    setResumeBusy(true);
    try {
      const r = await api.uploadResume(file);
      setResumeSummary(r.summary);
      setUseResume(true);
    } catch (e: any) {
      setStartError(e.message || "Could not upload resume.");
    } finally {
      setResumeBusy(false);
    }
  };

  const refreshEntitlement = () =>
    api.entitlement().then(setEntitlement).catch(() => {});

  const track = tracks.find((t) => t.id === trackId);
  const isDesign = ["system_design", "lld", "case_study"].includes(focus);

  // keep focus valid when track changes
  useEffect(() => {
    if (track && !track.focuses.some((f) => f.id === focus)) {
      setFocus(track.focuses[0]?.id || "");
    }
  }, [trackId, tracks]);

  const companyName = () =>
    companyId === "__custom__" ? customCompany : undefined;
  const companyIdArg = () => (companyId === "__custom__" ? undefined : companyId);

  const beginCall = async () => {
    setReport(null);
    setLastHint(null);
    setHintsUsed(0);
    setPenalty(0);
    // create a server session (also used for hints + grading context).
    // This is the PAID gate: a 402 means the free quota is used up -> paywall.
    let s: any;
    try {
      s = await api.startSession({
        username,
        mode: "interview",
        track: trackId,
        focus,
        difficulty,
        role: role || undefined,
        company_id: companyIdArg(),
        company_name: companyName(),
        hints_enabled: hintsEnabled,
      });
    } catch (e: any) {
      const status = e?.status;
      if (status === 402) {
        // Paywall: free quota used up. Show pricing with the server's message.
        setPaywallReason(
          e?.detail?.message ||
            "You've used your free interviews. Buy credits to keep practicing."
        );
        if (e?.detail?.entitlement) setEntitlement(e.detail.entitlement);
        setPaywall(true);
      } else if (status === 401) {
        // Interviews require a real account (guests can't start one).
        setStartError(
          "Please log in or sign up to start an interview. " +
            "(Interviews need an account so we can save your progress and credits.)"
        );
      } else {
        setStartError(e?.message || "Could not start the interview.");
      }
      setStarted(false);
      return;
    }
    setSessionId(s.session_id);
    if (s.entitlement) setEntitlement(s.entitlement);
    call.start({
      username,
      mode: "interview",
      session_id: s.session_id,
      track: trackId,
      focus,
      difficulty,
      role: role || undefined,
      company_id: companyIdArg(),
      company_name: companyName(),
      candidate_note: note || undefined,
      hints_enabled: hintsEnabled,
      use_resume: useResume,
      job_description: jobDesc || undefined,
    });
  };

  const askHint = async (tier: number) => {
    if (!sessionId) return;
    setHintLoading(true);
    try {
      const res = await api.requestHint(sessionId, {
        tier,
        transcript: call.cleanTranscript(),
        question_context: note || undefined,
      });
      setLastHint(res);
      setHintsUsed(res.hints_used);
      setPenalty(res.total_penalty);
    } catch (e: any) {
      setLastHint({ text: e.message, label: "Error", penalty: 0 });
    } finally {
      setHintLoading(false);
    }
  };

  const endAndGrade = async () => {
    call.stop();
    const transcript = call.cleanTranscript();
    if (transcript.length === 0) {
      setStarted(false);
      return;
    }
    setGrading(true);
    try {
      const res = await api.gradeInterview({
        username,
        session_id: sessionId,
        track: trackId,
        role: role || undefined,
        focus,
        difficulty,
        company_id: companyIdArg(),
        company_name: companyName(),
        transcript,
      });
      setReport({ ...res, role: role || track?.name, focus, difficulty });
    } catch (e: any) {
      setReport({
        overall_score: 0,
        scores: {},
        strengths: [],
        improvements: [],
        feedback: `Could not grade: ${e.message}`,
        focus,
        difficulty,
      });
    } finally {
      setGrading(false);
    }
  };

  // ---------------- report view ----------------
  if (report) {
    return (
      <div className="space-y-4">
        <ReportCard report={report} />
        <CoachingCard
          report={report}
          transcript={call.cleanTranscript()}
          sessionId={sessionId}
          onDrill={(f, d) => {
            setReport(null);
            setStarted(false);
            setFocus(f);
            setDifficulty(d);
          }}
        />
        <div className="flex gap-3">
          <button
            onClick={() => {
              setReport(null);
              setStarted(false);
            }}
            className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500"
          >
            New interview
          </button>
          <button
            onClick={() => nav("/progress")}
            className="px-5 py-2 rounded-xl bg-white/10 hover:bg-white/20"
          >
            View progress
          </button>
        </div>
      </div>
    );
  }

  // ---------------- setup view ----------------
  if (!started) {
    return (
      <div className="max-w-2xl">
        {paywall && (
          <Pricing
            reason={
              paywallReason ||
              "You've used your free interviews. Buy credits to keep practicing."
            }
            onClose={() => {
              setPaywall(false);
              setPaywallReason("");
            }}
            onPaid={() => {
              setPaywall(false);
              refreshEntitlement();
            }}
          />
        )}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold">Mock Interview 🎯</h1>
            <p className="text-gray-400 mt-1">
              Configure a realistic interview. A real-sounding interviewer will
              call you, ask real (and tough) questions, optionally give hints, and
              grade you.
            </p>
          </div>
          {entitlement && (
            <div className="text-right shrink-0 ml-4">
              <div className="text-xs text-gray-400">Your interviews</div>
              <div className="text-sm font-medium">
                {entitlement.free_remaining > 0 && (
                  <span className="text-green-300">
                    {entitlement.free_remaining} free left
                  </span>
                )}
                {entitlement.credits > 0 && (
                  <span className="text-brand-300">
                    {entitlement.free_remaining > 0 ? " · " : ""}
                    {entitlement.credits} credits
                  </span>
                )}
                {entitlement.free_remaining === 0 &&
                  entitlement.credits === 0 && (
                    <span className="text-yellow-300">none left</span>
                  )}
              </div>
              <button
                onClick={() => setPaywall(true)}
                className="mt-1 text-xs text-brand-400 hover:underline"
              >
                Buy credits
              </button>
            </div>
          )}
        </div>

        {startError && (
          <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 flex items-center justify-between gap-3">
            <span>{startError}</span>
            <button
              onClick={() => nav("/")}
              className="shrink-0 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs"
            >
              Log in / Sign up
            </button>
          </div>
        )}

        <div className="mt-6 space-y-5">
          {/* Track */}
          <div>
            <label className="text-sm text-gray-300">Track</label>
            <div className="mt-1 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {tracks.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTrackId(t.id)}
                  className={`px-3 py-2 rounded-xl text-sm text-left border ${
                    trackId === t.id
                      ? "bg-brand-600 border-brand-500"
                      : "bg-white/5 border-white/10 hover:bg-white/10"
                  }`}
                >
                  {t.emoji} {t.name}
                </button>
              ))}
            </div>
          </div>

          {/* Focus */}
          {track && (
            <div>
              <label className="text-sm text-gray-300">Focus area</label>
              <div className="mt-1 grid grid-cols-2 gap-2">
                {track.focuses.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFocus(f.id)}
                    title={f.brief}
                    className={`px-3 py-2 rounded-xl text-sm text-left border ${
                      focus === f.id
                        ? "bg-brand-600 border-brand-500"
                        : "bg-white/5 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    {focusLabel(f.id)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Design topic suggestions */}
          {isDesign && (
            <div>
              <label className="text-sm text-gray-300">
                Design topic (optional — staged system → implementation drill-down)
              </label>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Design a payment gateway"
                className="mt-1 w-full px-4 py-2 rounded-xl bg-white/10 border border-white/10 outline-none"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {designTopics.map((d) => (
                  <button
                    key={d}
                    onClick={() => setNote(`Design a ${d.toLowerCase()}`)}
                    className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-xs hover:bg-white/10"
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Company */}
          <div>
            <label className="text-sm text-gray-300">Company / board</label>
            <div className="mt-1 flex flex-wrap gap-2">
              {companies.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCompanyId(c.id)}
                  className={`px-3 py-1.5 rounded-xl text-sm border ${
                    companyId === c.id
                      ? "bg-brand-600 border-brand-500"
                      : "bg-white/5 border-white/10 hover:bg-white/10"
                  }`}
                >
                  {c.name}
                </button>
              ))}
              <button
                onClick={() => setCompanyId("__custom__")}
                className={`px-3 py-1.5 rounded-xl text-sm border ${
                  companyId === "__custom__"
                    ? "bg-brand-600 border-brand-500"
                    : "bg-white/5 border-white/10 hover:bg-white/10"
                }`}
              >
                Other…
              </button>
            </div>
            {companyId === "__custom__" && (
              <input
                value={customCompany}
                onChange={(e) => setCustomCompany(e.target.value)}
                placeholder="Type any company (e.g. Netflix, Stripe)"
                className="mt-2 w-full px-4 py-2 rounded-xl bg-white/10 border border-white/10 outline-none"
              />
            )}
          </div>

          {/* Difficulty */}
          <div>
            <label className="text-sm text-gray-300">Difficulty</label>
            <div className="mt-1 flex gap-2">
              {difficulties.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setDifficulty(d.id)}
                  title={d.question}
                  className={`px-4 py-2 rounded-xl text-sm border ${
                    difficulty === d.id
                      ? "bg-brand-600 border-brand-500"
                      : "bg-white/5 border-white/10 hover:bg-white/10"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Role + hints */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-300">Role (optional)</label>
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder={track?.name || "e.g. Senior Backend Engineer"}
                className="mt-1 w-full px-4 py-2 rounded-xl bg-white/10 border border-white/10 outline-none"
              />
            </div>
            <div>
              <label className="text-sm text-gray-300">Hints</label>
              <button
                onClick={() => setHintsEnabled((v) => !v)}
                className={`mt-1 w-full px-4 py-2 rounded-xl text-sm border ${
                  hintsEnabled
                    ? "bg-green-600/30 border-green-500"
                    : "bg-white/5 border-white/10"
                }`}
              >
                {hintsEnabled
                  ? "Enabled — hints cost points (realistic)"
                  : "Disabled — no help, no penalty"}
              </button>
            </div>
          </div>

          {/* Resume / JD tailoring */}
          <div className="rounded-xl bg-white/5 border border-white/10 p-4">
            <div className="text-sm font-medium">
              📄 Tailor to your resume{" "}
              <span className="text-xs text-gray-500">(optional)</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Upload your resume and the interviewer will ask questions based on
              your real experience and target role.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm cursor-pointer">
                {resumeBusy
                  ? "Reading…"
                  : resumeSummary
                  ? "Replace resume"
                  : "Upload PDF/DOCX"}
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadResume(f);
                  }}
                />
              </label>
              {resumeSummary && (
                <label className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={useResume}
                    onChange={(e) => setUseResume(e.target.checked)}
                  />
                  Use my resume
                </label>
              )}
            </div>
            {resumeSummary && (
              <div className="mt-2 text-xs text-gray-400">{resumeSummary}</div>
            )}
            <input
              value={jobDesc}
              onChange={(e) => setJobDesc(e.target.value)}
              placeholder="Target role / job description (optional)"
              className="mt-3 w-full px-3 py-2 rounded-lg bg-white/10 border border-white/10 outline-none text-sm"
            />
          </div>

          <button
            onClick={() => setStarted(true)}
            className="w-full py-3 rounded-xl bg-green-600 hover:bg-green-500 font-medium"
          >
            Enter interview room →
          </button>
        </div>
      </div>
    );
  }

  // ---------------- interview room ----------------
  const companyLabel =
    companyId === "__custom__"
      ? customCompany || "Custom"
      : companies.find((c) => c.id === companyId)?.name || companyId;

  return (
    <div>
      <button onClick={() => setStarted(false)} className="text-sm text-gray-400 mb-4">
        ← Back to setup
      </button>
      <div className="mb-3 flex items-center gap-2 text-xs">
        <span className="px-2 py-1 rounded-full bg-white/10 text-gray-300">
          {engine === "realtime"
            ? "🎧 Realtime voice"
            : "🗣️ Browser voice (free, on-device)"}
        </span>
        {engine === "browser" && !browserSupported && (
          <span className="text-red-400">
            Your browser lacks speech support — use Chrome, Edge or Safari.
          </span>
        )}
        {engine === "browser" && browserSupported && (
          <span className="text-gray-500">
            Speak naturally; it listens hands-free and replies aloud.
          </span>
        )}
      </div>
      <CallStage
        title="Interviewer"
        subtitle={`${companyLabel} · ${track?.name} · ${focusLabel(focus)} · ${difficulty}`}
        avatar="🧑‍💼"
        status={call.status}
        error={call.error}
        transcript={call.transcript}
        aiSpeaking={call.aiSpeaking}
        userSpeaking={(call as any).userSpeaking}
        interimText={(call as any).interimText}
        onStart={beginCall}
        onStop={endAndGrade}
        onToggleMute={call.toggleMute}
        primaryLabel="🎙️ Start interview"
        endLabel="End & get feedback"
        footer={
          call.status === "live" && hintsEnabled ? (
            <div className="mt-5 w-full">
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setHintOpen((v) => !v)}
                  className="px-4 py-2 rounded-full bg-yellow-500/20 border border-yellow-500/40 text-sm text-yellow-200 hover:bg-yellow-500/30"
                >
                  💡 Need a hint?
                </button>
                {hintsUsed > 0 && (
                  <span className="text-xs text-yellow-300">
                    {hintsUsed} hint{hintsUsed > 1 ? "s" : ""} · −{penalty} pts
                  </span>
                )}
              </div>
              {hintOpen && (
                <div className="mt-3 rounded-xl bg-black/30 border border-white/10 p-3">
                  <div className="text-xs text-gray-400 mb-2">
                    More reveal = bigger score cost:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {hintTiers.map((h) => (
                      <button
                        key={h.tier}
                        disabled={hintLoading}
                        onClick={() => askHint(h.tier)}
                        className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm disabled:opacity-50"
                      >
                        {h.label}{" "}
                        <span className="text-yellow-300">−{h.penalty}</span>
                      </button>
                    ))}
                  </div>
                  {hintLoading && (
                    <p className="mt-2 text-sm text-gray-400">Thinking…</p>
                  )}
                  {lastHint && !hintLoading && (
                    <div className="mt-3 text-sm">
                      <span className="text-yellow-300 font-medium">
                        {lastHint.label} (−{lastHint.penalty}):{" "}
                      </span>
                      {lastHint.text}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null
        }
      />

      {/* Type-to-interviewer fallback: always works, even if speech is flaky. */}
      {call.status === "live" && (
        <div className="mt-4 flex gap-2">
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && typed.trim()) {
                (call as any).sendText?.(typed.trim());
                setTyped("");
              }
            }}
            placeholder="Or type your answer to the interviewer…"
            className="flex-1 px-4 py-2 rounded-xl bg-white/10 border border-white/10 outline-none focus:border-brand-500"
          />
          <button
            onClick={() => {
              if (typed.trim()) {
                (call as any).sendText?.(typed.trim());
                setTyped("");
              }
            }}
            className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-sm"
          >
            Send
          </button>
        </div>
      )}

      {/* Coding round: editor + tests. Design round: whiteboard.
          Shown once the session exists, independent of the voice call so the
          candidate can code/draw even if mic/voice isn't available. */}
      {sessionId && call.status !== "idle" && focus === "dsa" && (
        <div className="mt-6">
          <CodePanel sessionId={sessionId} />
        </div>
      )}
      {sessionId &&
        call.status !== "idle" &&
        (focus === "system_design" || focus === "lld") && (
          <div className="mt-6">
            <Whiteboard
              sessionId={sessionId}
              onReaction={(msg) => (call as any).injectAssistant?.(msg)}
            />
          </div>
        )}

      {grading && (
        <p className="mt-4 text-sm text-yellow-300">
          Grading your interview like a real reviewer…
        </p>
      )}
    </div>
  );
}
