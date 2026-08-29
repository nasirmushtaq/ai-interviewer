import { useEffect, useState } from "react";
import { api } from "../api";
import { useRealtimeCall } from "./useRealtimeCall";
import { useBrowserVoiceCall, browserVoiceSupported } from "./useBrowserVoiceCall";

export type VoiceEngine = "realtime" | "browser";

/**
 * Picks the voice engine: the low-latency cloud Realtime API when the server
 * has it configured, otherwise the free on-device browser voice (Web Speech).
 * Both hooks expose the same interface, so callers use `call` uniformly.
 */
export function useVoiceCall() {
  const [engine, setEngine] = useState<VoiceEngine | null>(null);
  const realtime = useRealtimeCall();
  const browser = useBrowserVoiceCall();

  useEffect(() => {
    let cancelled = false;
    api
      .config()
      .then((cfg) => {
        if (cancelled) return;
        // Prefer realtime only if the server supports it AND we can reach it.
        setEngine(cfg?.realtime_available ? "realtime" : "browser");
      })
      .catch(() => !cancelled && setEngine("browser"));
    return () => {
      cancelled = true;
    };
  }, []);

  const call = engine === "realtime" ? realtime : browser;

  return {
    engine,
    ready: engine !== null,
    browserSupported: browserVoiceSupported(),
    call,
  };
}
