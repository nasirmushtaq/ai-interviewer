import { useCallback, useRef, useState } from "react";
import { Excalidraw, exportToBlob } from "@excalidraw/excalidraw";
import { api } from "../api";
import { extractDiagram } from "../lib/diagram";

async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const r = new FileReader();
    r.onloadend = () => resolve(r.result as string);
    r.readAsDataURL(blob);
  });
}

/**
 * In-app system-design whiteboard. Periodically (and on demand) snapshots the
 * canvas to a PNG and sends it to the backend, which runs GPT-4o vision so the
 * interviewer can "see" the diagram.
 */
export default function Whiteboard({
  sessionId,
  onReaction,
}: {
  sessionId: string;
  onReaction?: (message: string) => void;
}) {
  const apiRef = useRef<any>(null);
  const [sharing, setSharing] = useState(false);
  const [lastNote, setLastNote] = useState<string>("");
  const [gaps, setGaps] = useState<string[]>([]);
  const [auto, setAuto] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [height, setHeight] = useState(420);
  const timerRef = useRef<any>(null);
  const lastSentRef = useRef<string>(""); // structural fingerprint last sent

  // Compact fingerprint of the graph so we can skip no-op / cosmetic updates.
  const fingerprint = (s: any): string => {
    const comps = (s.components || [])
      .map((c: any) => c.label)
      .sort()
      .join("|");
    const edges = (s.edges || [])
      .map((e: any) => `${e.from}>${e.to}`)
      .sort()
      .join("|");
    return `${comps}#${edges}`;
  };

  const snapshot = useCallback(
    async (final = false, opts?: { silentIfUnchanged?: boolean }) => {
      const excalidraw = apiRef.current;
      if (!excalidraw) return;
      const elements = excalidraw.getSceneElements();
      const structure = extractDiagram(elements as any[]);
      const fp = fingerprint(structure);
      // Auto-share: skip entirely if the architecture hasn't structurally changed.
      if (opts?.silentIfUnchanged && fp === lastSentRef.current && !final) {
        return;
      }
      setSharing(true);
      try {
        const blob = await exportToBlob({
          elements,
          appState: excalidraw.getAppState(),
          files: excalidraw.getFiles(),
          mimeType: "image/png",
          exportPadding: 8,
        });
        const dataUrl = await blobToDataUrl(blob);
        const res = await api.submitDiagram(sessionId, {
          image: dataUrl,
          structure,
          final,
        });
        lastSentRef.current = fp;
        setLastNote(res.summary || res.note || "");
        setGaps(res.gaps || []);
        // The interviewer speaks up ONLY when the backend decided a reaction is
        // warranted for a meaningful change. Otherwise it stays silent.
        if (res.reaction && onReaction) onReaction(res.reaction);
      } catch (e: any) {
        setLastNote(`(share failed: ${e.message})`);
      } finally {
        setSharing(false);
      }
    },
    [sessionId, onReaction]
  );

  const toggleAuto = () => {
    if (auto) {
      clearInterval(timerRef.current);
      setAuto(false);
    } else {
      setAuto(true);
      // Poll more often, but only actually send when the design changed.
      timerRef.current = setInterval(
        () => snapshot(false, { silentIfUnchanged: true }),
        8000
      );
    }
  };

  return (
    <div
      className={`rounded-2xl bg-white/5 border border-white/10 p-3 ${
        fullscreen ? "fixed inset-3 z-50 flex flex-col" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-sm text-gray-300">
          🖊️ Design whiteboard — draw your architecture
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => snapshot(false)}
            disabled={sharing}
            className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-sm disabled:opacity-50"
          >
            {sharing ? "Sharing…" : "👁️ Share with interviewer"}
          </button>
          <button
            onClick={toggleAuto}
            className={`px-3 py-1.5 rounded-lg text-sm border ${
              auto
                ? "bg-green-600/30 border-green-500"
                : "bg-white/5 border-white/10 hover:bg-white/10"
            }`}
          >
            {auto ? "👀 Interviewer watching" : "Let interviewer watch"}
          </button>
          <button
            onClick={() => setFullscreen((v) => !v)}
            className="px-3 py-1.5 rounded-lg text-sm bg-white/5 border border-white/10 hover:bg-white/10"
            title="Toggle fullscreen"
          >
            {fullscreen ? "🡴 Exit fullscreen" : "⛶ Fullscreen"}
          </button>
        </div>
      </div>

      {/* Resizable canvas: drag the bottom-right corner to resize. In
          fullscreen it fills the panel. */}
      <div
        className={`rounded-xl overflow-hidden bg-white ${
          fullscreen ? "flex-1" : "resize-y overflow-auto min-h-[16rem]"
        }`}
        style={fullscreen ? undefined : { height: `${height}px`, resize: "both" }}
      >
        <div className="w-full h-full">
          <Excalidraw
            excalidrawAPI={(a) => (apiRef.current = a)}
            initialData={{ appState: { viewBackgroundColor: "#ffffff" } }}
          />
        </div>
      </div>

      {!fullscreen && (
        <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
          <span>Drag the bottom-right corner to resize ↘</span>
          <button onClick={() => setHeight(320)} className="hover:text-gray-300">
            Small
          </button>
          <button onClick={() => setHeight(520)} className="hover:text-gray-300">
            Medium
          </button>
          <button onClick={() => setHeight(760)} className="hover:text-gray-300">
            Large
          </button>
        </div>
      )}

      {lastNote && (
        <div className="mt-2 text-xs text-gray-400">
          Interviewer sees: <span className="text-brand-300">{lastNote}</span>
        </div>
      )}
      {gaps.length > 0 && (
        <div className="mt-1 text-xs text-gray-500">
          Areas the interviewer may probe:{" "}
          <span className="text-yellow-300/80">{gaps.slice(0, 3).join(" · ")}</span>
        </div>
      )}
    </div>
  );
}
