import { useCallback, useRef, useState } from "react";
import { api, Turn } from "../api";

export type CallStatus = "idle" | "connecting" | "live" | "error" | "ended";

/**
 * Connects the browser directly to the OpenAI Realtime API over WebRTC using an
 * ephemeral token minted by our backend. Streams mic audio up, plays the AI
 * voice down, and surfaces a live transcript of both sides.
 */
export function useRealtimeCall() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [error, setError] = useState<string>("");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [aiSpeaking, setAiSpeaking] = useState(false);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const micRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // accumulate streaming deltas per item id
  const assistantBuf = useRef<Record<string, string>>({});

  const pushUser = (text: string) =>
    setTranscript((t) => [...t, { role: "user", text }]);

  const upsertAssistant = (id: string, text: string) =>
    setTranscript((t) => {
      const idx = t.findIndex((x) => (x as any)._id === id);
      const entry = { role: "assistant", text, _id: id } as any;
      if (idx === -1) return [...t, entry];
      const copy = [...t];
      copy[idx] = entry;
      return copy;
    });

  const handleEvent = useCallback((ev: MessageEvent) => {
    let msg: any;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    switch (msg.type) {
      case "response.audio_transcript.delta": {
        const id = msg.item_id || msg.response_id || "cur";
        assistantBuf.current[id] = (assistantBuf.current[id] || "") + (msg.delta || "");
        upsertAssistant(id, assistantBuf.current[id]);
        setAiSpeaking(true);
        break;
      }
      case "response.audio_transcript.done": {
        const id = msg.item_id || msg.response_id || "cur";
        if (msg.transcript) upsertAssistant(id, msg.transcript);
        break;
      }
      case "response.done":
        setAiSpeaking(false);
        break;
      case "conversation.item.input_audio_transcription.completed": {
        if (msg.transcript && msg.transcript.trim()) pushUser(msg.transcript.trim());
        break;
      }
      default:
        break;
    }
  }, []);

  const start = useCallback(
    async (sessionPayload: any) => {
      setError("");
      setTranscript([]);
      assistantBuf.current = {};
      setStatus("connecting");
      try {
        const session = await api.realtimeSession(sessionPayload);
        const ephemeralKey = session?.client_secret?.value;
        const model = session?.model;
        // Backend provides the correct WebRTC endpoint for OpenAI or Azure.
        const webrtcUrl =
          session?.webrtc_url ||
          `https://api.openai.com/v1/realtime?model=${encodeURIComponent(model)}`;
        if (!ephemeralKey) throw new Error("No ephemeral key returned by server.");

        const pc = new RTCPeerConnection();
        pcRef.current = pc;

        // remote audio playback
        const audioEl = new Audio();
        audioEl.autoplay = true;
        audioRef.current = audioEl;
        pc.ontrack = (e) => {
          audioEl.srcObject = e.streams[0];
        };

        // mic
        const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
        micRef.current = mic;
        mic.getTracks().forEach((track) => pc.addTrack(track, mic));

        // data channel for events / transcripts
        const dc = pc.createDataChannel("oai-events");
        dcRef.current = dc;
        dc.onmessage = handleEvent;

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const resp = await fetch(webrtcUrl, {
          method: "POST",
          body: offer.sdp,
          headers: {
            Authorization: `Bearer ${ephemeralKey}`,
            "Content-Type": "application/sdp",
          },
        });
        const answerSdp = await resp.text();
        if (!resp.ok) throw new Error(answerSdp || "Realtime handshake failed.");
        await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

        pc.onconnectionstatechange = () => {
          if (["failed", "disconnected", "closed"].includes(pc.connectionState)) {
            setStatus((s) => (s === "ended" ? s : "error"));
          }
        };
        setStatus("live");
      } catch (e: any) {
        setError(e.message || String(e));
        setStatus("error");
      }
    },
    [handleEvent]
  );

  const stop = useCallback(() => {
    dcRef.current?.close();
    micRef.current?.getTracks().forEach((t) => t.stop());
    pcRef.current?.close();
    pcRef.current = null;
    setAiSpeaking(false);
    setStatus("ended");
  }, []);

  const toggleMute = useCallback((muted: boolean) => {
    micRef.current?.getAudioTracks().forEach((t) => (t.enabled = !muted));
  }, []);

  const cleanTranscript = (): Turn[] =>
    transcript.map((t) => ({ role: t.role, text: t.text }));

  // Text input isn't used in realtime mode (audio is streamed); no-op for a
  // uniform interface with the browser-voice hook.
  const sendText = (_text: string) => {};

  return { status, error, transcript, aiSpeaking, interimText: "", start, stop, toggleMute, sendText, injectAssistant: (_t: string) => {}, cleanTranscript };
}
