import { useEffect, useRef, useState } from "react";
import { Turn } from "../api";
import { CallStatus } from "../hooks/useRealtimeCall";

export default function CallStage({
  title,
  subtitle,
  avatar,
  status,
  error,
  transcript,
  aiSpeaking,
  userSpeaking = false,
  interimText,
  onStart,
  onStop,
  onToggleMute,
  primaryLabel = "Start call",
  endLabel = "End call",
  footer,
}: {
  title: string;
  subtitle?: string;
  avatar: string;
  status: CallStatus;
  error: string;
  transcript: Turn[];
  aiSpeaking: boolean;
  userSpeaking?: boolean;
  interimText?: string;
  onStart: () => void;
  onStop: () => void;
  onToggleMute: (m: boolean) => void;
  primaryLabel?: string;
  endLabel?: string;
  footer?: React.ReactNode;
}) {
  const [muted, setMuted] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [transcript]);

  const live = status === "live";
  const connecting = status === "connecting";

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Call panel */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-6 flex flex-col items-center">
        <div
          className={`relative w-32 h-32 rounded-full flex items-center justify-center text-6xl bg-brand-600/30 ${
            aiSpeaking ? "pulse-ring" : ""
          }`}
        >
          {avatar}
        </div>
        <h2 className="mt-4 text-xl font-semibold">{title}</h2>
        {subtitle && <p className="text-sm text-gray-400 text-center">{subtitle}</p>}

        <div className="mt-3 text-sm">
          {status === "idle" && <span className="text-gray-400">Ready to connect</span>}
          {connecting && <span className="text-yellow-400">Connecting…</span>}
          {live && (
            <span className="text-green-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              {aiSpeaking
                ? "Speaking…"
                : userSpeaking
                  ? "Listening — go ahead…"
                  : "Listening…"}
            </span>
          )}
          {status === "ended" && <span className="text-gray-400">Call ended</span>}
          {status === "error" && <span className="text-red-400">Error</span>}
        </div>

        {error && (
          <p className="mt-2 text-xs text-red-400 text-center max-w-xs">{error}</p>
        )}

        <div className="mt-6 flex gap-3">
          {!live ? (
            <button
              onClick={onStart}
              disabled={connecting}
              className="px-6 py-3 rounded-full bg-green-600 hover:bg-green-500 font-medium disabled:opacity-50"
            >
              {connecting ? "Connecting…" : primaryLabel}
            </button>
          ) : (
            <>
              <button
                onClick={() => {
                  const m = !muted;
                  setMuted(m);
                  onToggleMute(m);
                }}
                className="px-5 py-3 rounded-full bg-white/10 hover:bg-white/20 font-medium"
              >
                {muted ? "🔇 Unmute" : "🎙️ Mute"}
              </button>
              <button
                onClick={onStop}
                className="px-6 py-3 rounded-full bg-red-600 hover:bg-red-500 font-medium"
              >
                ☎️ {endLabel}
              </button>
            </>
          )}
        </div>
        {footer}
      </div>

      {/* Transcript */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-4 flex flex-col h-[28rem]">
        <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">
          Live transcript
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 pr-1">
          {transcript.length === 0 && (
            <p className="text-gray-500 text-sm">
              Your conversation will appear here as you speak.
            </p>
          )}
          {transcript.map((t, i) => (
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
          {interimText && (
            <div className="ml-auto max-w-[85%] px-3 py-2 rounded-2xl rounded-br-sm text-sm bg-brand-600/40 text-white/80 italic">
              {interimText}…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
