import { useCallback, useRef, useState } from "react";
import { api, Turn } from "../api";

export type CallStatus = "idle" | "connecting" | "live" | "error" | "ended";

// Minimal typings for the (vendor-prefixed) Web Speech API.
type SpeechRecognition = any;
function getRecognitionCtor(): any {
  return (
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition ||
    null
  );
}

export function browserVoiceSupported(): boolean {
  return !!getRecognitionCtor() && "speechSynthesis" in window;
}

/**
 * A "voice call" built from free, on-device browser capabilities:
 *  - SpeechRecognition (continuous) transcribes the mic to text,
 *  - each finalized utterance is sent to the AI via /api/chat,
 *  - speechSynthesis speaks the AI's reply aloud.
 *
 * Exposes the same interface as useRealtimeCall so it drops into CallStage.
 */
export function useBrowserVoiceCall() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [interimText, setInterimText] = useState("");

  const recogRef = useRef<SpeechRecognition | null>(null);
  const payloadRef = useRef<any>(null);
  const historyRef = useRef<Turn[]>([]);
  const mutedRef = useRef(false);
  const busyRef = useRef(false); // waiting on AI or speaking -> don't send
  const pendingRef = useRef(""); // user speech buffered while AI is busy
  const stoppedRef = useRef(false);
  const recogRunningRef = useRef(false); // is SpeechRecognition currently active?
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  const pushTurn = (t: Turn) => {
    historyRef.current = [...historyRef.current, t];
    setTranscript([...historyRef.current]);
  };

  // Start recognition safely: Chrome throws if start() is called while already
  // running, and can get stuck if start/stop race. Guard with a running flag and
  // retry shortly if it's mid-teardown.
  const safeStartRecog = () => {
    const recog = recogRef.current;
    if (!recog || stoppedRef.current || recogRunningRef.current) return;
    try {
      recog.start();
      recogRunningRef.current = true;
    } catch {
      setTimeout(() => {
        if (!stoppedRef.current && !recogRunningRef.current) {
          try {
            recogRef.current?.start();
            recogRunningRef.current = true;
          } catch {}
        }
      }, 300);
    }
  };

  const speak = useCallback((text: string) => {
    return new Promise<void>((resolve) => {
      if (!("speechSynthesis" in window) || !text.trim()) return resolve();
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        setAiSpeaking(false);
        resolve();
      };
      // Safety: Chrome sometimes never fires onend/onerror (voices not ready,
      // tab throttling, long text). Estimate a max duration and force-resolve so
      // the conversation loop can never hang.
      const maxMs = Math.min(60000, 2500 + text.length * 90);
      const guard = setTimeout(finish, maxMs);

      const u = new SpeechSynthesisUtterance(text);
      if (voiceRef.current) u.voice = voiceRef.current;
      u.rate = 1.03;
      u.pitch = 1.0;
      u.onstart = () => setAiSpeaking(true);
      u.onend = () => {
        clearTimeout(guard);
        finish();
      };
      u.onerror = () => {
        clearTimeout(guard);
        finish();
      };
      try {
        window.speechSynthesis.cancel(); // clear any stuck queue
        window.speechSynthesis.speak(u);
        // Chrome bug: speech can start "paused"; nudge it.
        window.speechSynthesis.resume();
      } catch {
        clearTimeout(guard);
        finish();
      }
    });
  }, []);

  const handleUtterance = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (!clean || stoppedRef.current) return;
      // If the AI is currently busy (thinking/speaking), don't DROP the user's
      // speech — buffer it and process once free, so nothing is lost.
      if (busyRef.current) {
        pendingRef.current = pendingRef.current
          ? pendingRef.current + " " + clean
          : clean;
        return;
      }
      busyRef.current = true;
      pushTurn({ role: "user", text: clean });
      setInterimText("");
      try {
        const res = await api.chat({
          ...payloadRef.current,
          history: historyRef.current
            .slice(0, -1)
            .map((t) => ({ role: t.role, text: t.text })),
          message: clean,
        });
        const reply = res.reply || "";
        pushTurn({ role: "assistant", text: reply });
        // Pause recognition while the AI speaks so it doesn't hear itself.
        try {
          recogRef.current?.stop();
          recogRunningRef.current = false;
        } catch {}
        await speak(reply);
        if (!stoppedRef.current) {
          safeStartRecog();
        }
      } catch (e: any) {
        setError(e.message || String(e));
      } finally {
        busyRef.current = false;
        // Flush anything the user said while we were busy.
        const pending = pendingRef.current;
        pendingRef.current = "";
        if (pending && !stoppedRef.current) {
          handleUtterance(pending);
        }
      }
    },
    [speak]
  );

  const start = useCallback(
    async (sessionPayload: any) => {
      setError("");
      setTranscript([]);
      historyRef.current = [];
      stoppedRef.current = false;
      busyRef.current = false;
      payloadRef.current = sessionPayload;
      setStatus("connecting");

      const Ctor = getRecognitionCtor();
      if (!Ctor || !("speechSynthesis" in window)) {
        // No speech support: run a text-only interview so the editor/whiteboard
        // and the interviewer greeting still work.
        setError(
          "Voice isn't supported in this browser — running in text mode. " +
            "Use Chrome or Edge for the spoken experience."
        );
        setStatus("live");
        busyRef.current = true;
        try {
          const res = await api.chat({
            ...sessionPayload,
            history: [],
            message: "The interview is starting. Greet me, introduce yourself, and ask me to introduce myself before the first question.",
          });
          pushTurn({ role: "assistant", text: res.reply || "Let's get started." });
        } catch {
          /* ignore */
        } finally {
          busyRef.current = false;
        }
        return;
      }

      // Pick a decent English voice if available.
      const pickVoice = () => {
        const voices = window.speechSynthesis.getVoices();
        voiceRef.current =
          voices.find((v) => /en(-|_)?(US|GB)/i.test(v.lang) && /female|natural|samantha|google/i.test(v.name)) ||
          voices.find((v) => v.lang.toLowerCase().startsWith("en")) ||
          voices[0] ||
          null;
      };
      pickVoice();
      window.speechSynthesis.onvoiceschanged = pickVoice;

      // Go LIVE immediately so we can never hang on "connecting". The mic
      // pre-warm below is best-effort and time-boxed; SpeechRecognition manages
      // the actual microphone in Chrome regardless.
      setStatus("live");

      // Best-effort mic pre-warm to trigger the permission prompt. Time-boxed so
      // a dismissed/ignored prompt (which never resolves in Chrome) can't hang us.
      try {
        if (navigator.mediaDevices?.getUserMedia) {
          const stream = await Promise.race([
            navigator.mediaDevices.getUserMedia({ audio: true }),
            new Promise<MediaStream>((_, rej) =>
              setTimeout(() => rej(new Error("mic-timeout")), 8000)
            ),
          ]);
          stream.getTracks().forEach((t) => t.stop());
        }
      } catch (err: any) {
        // Ignore timeouts/transient errors — SpeechRecognition may still work.
        // A hard denial just means no voice input; text mode still works.
        if (err?.name === "NotAllowedError" || err?.name === "SecurityError") {
          setError(
            "Microphone is blocked — you can still type your answers. " +
              "Allow the mic for this site in Chrome to use voice."
          );
        }
      }

      const Ctor2 = getRecognitionCtor();
      if (!Ctor2) {
        // Shouldn't happen (checked earlier), but never leave the user stuck:
        // run text mode with the greeting.
        busyRef.current = true;
        try {
          const res = await api.chat({
            ...sessionPayload,
            history: [],
            message: "The interview is starting. Greet me, introduce yourself, and ask me to introduce myself before the first question.",
          });
          pushTurn({ role: "assistant", text: res.reply || "Let's get started." });
        } catch {
          /* ignore */
        } finally {
          busyRef.current = false;
        }
        return;
      }

      const recog: SpeechRecognition = new Ctor2();
      recog.lang = "en-US";
      recog.continuous = true;
      recog.interimResults = true;
      recogRef.current = recog;

      let interim = "";
      recog.onresult = (event: any) => {
        interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const r = event.results[i];
          if (r.isFinal) {
            if (!mutedRef.current) handleUtterance(r[0].transcript);
          } else {
            interim += r[0].transcript;
          }
        }
        // Live feedback so the user can SEE it's hearing them.
        setInterimText(mutedRef.current ? "" : interim);
      };
      recog.onstart = () => {
        recogRunningRef.current = true;
      };
      recog.onerror = (e: any) => {
        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
          setError(
            "Voice input is blocked — you can still type your answers. " +
              "Allow the microphone for this site to use voice."
          );
        } else if (e.error === "no-speech" || e.error === "aborted") {
          // normal — the onend handler will restart listening
        } else {
          // Surface unexpected errors (e.g. 'network', 'audio-capture') so the
          // user isn't left silently non-functional.
          setError(`Speech recognition error: ${e.error}. You can type instead.`);
        }
      };
      recog.onend = () => {
        recogRunningRef.current = false;
        // Keep listening unless the user hung up or the AI is speaking.
        if (!stoppedRef.current && !busyRef.current) {
          safeStartRecog();
        }
      };

      // NOTE: we do NOT start recognition here. It starts AFTER the greeting
      // finishes (below), to avoid a start()/stop() race that leaves Chrome's
      // SpeechRecognition in a stuck, silently-non-emitting state.
      setStatus("live");

      // Interviewer opens with a greeting/first question (non-blocking).
      busyRef.current = true;
      try {
        const res = await api.chat({
          ...sessionPayload,
          history: [],
          message:
            "The interview is starting. Greet me, introduce yourself, and ask me to introduce myself before the first question.",
        });
        const reply = res.reply || "Hello! Let's get started.";
        pushTurn({ role: "assistant", text: reply });
        await speak(reply);
      } catch (e: any) {
        setError(
          "Couldn't reach the interviewer to start talking: " +
            (e?.message || String(e))
        );
      } finally {
        busyRef.current = false;
        if (!stoppedRef.current) {
          safeStartRecog();
        }
      }
    },
    [handleUtterance, speak]
  );

  const stop = useCallback(() => {
    stoppedRef.current = true;
    try {
      recogRef.current?.stop();
    } catch {}
    try {
      window.speechSynthesis.cancel();
    } catch {}
    setAiSpeaking(false);
    setStatus("ended");
  }, []);

  const toggleMute = useCallback((muted: boolean) => {
    mutedRef.current = muted;
  }, []);

  // Typed input fallback — always works even if speech is unavailable/flaky.
  const sendText = useCallback(
    (text: string) => {
      if (text.trim()) handleUtterance(text);
    },
    [handleUtterance]
  );

  // Inject a proactive interviewer message (e.g. reacting to a diagram change)
  // into the conversation: add it to the transcript and speak it. Skipped while
  // the AI is already busy so it never talks over an in-flight turn.
  const injectAssistant = useCallback(
    async (text: string) => {
      const clean = (text || "").trim();
      if (!clean || stoppedRef.current || busyRef.current) return;
      busyRef.current = true;
      pushTurn({ role: "assistant", text: clean });
      try {
        recogRef.current?.stop();
        recogRunningRef.current = false;
      } catch {}
      await speak(clean);
      busyRef.current = false;
      if (!stoppedRef.current) safeStartRecog();
    },
    [speak]
  );

  const cleanTranscript = (): Turn[] =>
    historyRef.current.map((t) => ({ role: t.role, text: t.text }));

  return {
    status,
    error,
    transcript,
    aiSpeaking,
    // Parity with the realtime hook: the browser engine is "hearing" the
    // candidate whenever it has interim speech-recognition text.
    userSpeaking: interimText.length > 0,
    interimText,
    start,
    stop,
    toggleMute,
    sendText,
    injectAssistant,
    cleanTranscript,
  };
}
