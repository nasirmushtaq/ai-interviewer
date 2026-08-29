import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useUser } from "../user";
import { useVoiceCall } from "../hooks/useVoiceCall";
import CallStage from "../components/CallStage";

export default function Call() {
  const { personaId = "emma" } = useParams();
  const { username } = useUser();
  const nav = useNavigate();
  const [persona, setPersona] = useState<any>(null);
  const [saved, setSaved] = useState<{ summary: string; new_memories: string[] } | null>(
    null
  );
  const [saving, setSaving] = useState(false);
  const { engine, browserSupported, call } = useVoiceCall();

  useEffect(() => {
    api.personas().then((list: any[]) =>
      setPersona(list.find((p) => p.id === personaId) || list[0])
    );
  }, [personaId]);

  useEffect(() => {
    if (!username) nav("/");
  }, [username]);

  const start = () =>
    call.start({ username, mode: "persona", persona_id: personaId });

  const end = async () => {
    call.stop();
    const transcript = call.cleanTranscript();
    if (transcript.length === 0) return;
    setSaving(true);
    try {
      const res = await api.saveConversation({
        username,
        mode: "persona",
        persona_id: personaId,
        title: `Call with ${persona?.name || personaId}`,
        transcript,
      });
      setSaved(res);
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  };

  if (!persona) return <p>Loading…</p>;

  return (
    <div>
      <button onClick={() => nav("/")} className="text-sm text-gray-400 mb-4">
        ← Back
      </button>
      <div className="mb-3 text-xs">
        <span className="px-2 py-1 rounded-full bg-white/10 text-gray-300">
          {engine === "realtime"
            ? "🎧 Realtime voice"
            : "🗣️ Browser voice (free, on-device)"}
        </span>
        {engine === "browser" && !browserSupported && (
          <span className="ml-2 text-red-400">
            Use Chrome, Edge or Safari for speech.
          </span>
        )}
      </div>
      <CallStage
        title={persona.name}
        subtitle={persona.tagline}
        avatar={persona.avatar}
        status={call.status}
        error={call.error}
        transcript={call.transcript}
        aiSpeaking={call.aiSpeaking}
        interimText={(call as any).interimText}
        onStart={start}
        onStop={end}
        onToggleMute={call.toggleMute}
        primaryLabel="📞 Call"
      />

      {saving && <p className="mt-4 text-sm text-gray-400">Saving & remembering…</p>}
      {saved && (
        <div className="mt-6 rounded-2xl bg-white/5 border border-white/10 p-5">
          <h3 className="font-semibold">Call saved ✅</h3>
          {saved.summary && (
            <p className="text-sm text-gray-300 mt-1">{saved.summary}</p>
          )}
          {saved.new_memories?.length > 0 && (
            <div className="mt-3">
              <div className="text-xs uppercase text-gray-400">
                {persona.name} will now remember:
              </div>
              <ul className="mt-1 text-sm list-disc list-inside text-brand-300">
                {saved.new_memories.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
