/**
 * Extract a STRUCTURED architecture graph from Excalidraw scene elements.
 *
 * Excalidraw gives us shapes (rectangles/ellipses/diamonds), text (standalone or
 * bound to a shape via containerId), and arrows/lines with startBinding/endBinding
 * pointing at element ids. We turn that into components (labeled nodes) and edges
 * (directed connections), plus loose labels — a precise model the interviewer can
 * reason over ("all writes route through X", "queue between A and B", etc.).
 */

export type DiagramComponent = {
  id: string;
  label: string;
  shape: string;
};

export type DiagramEdge = {
  from: string; // component label (or "?")
  to: string;
  label?: string; // text on the arrow, if any
};

export type DiagramModel = {
  components: DiagramComponent[];
  edges: DiagramEdge[];
  loose_labels: string[];
  counts: { components: number; edges: number };
};

const SHAPE_TYPES = new Set(["rectangle", "ellipse", "diamond"]);

export function extractDiagram(elements: any[]): DiagramModel {
  const els = (elements || []).filter((e) => e && !e.isDeleted);

  // 1) Map text bound to containers, and collect standalone text.
  const textByContainer: Record<string, string> = {};
  const standaloneText: { id: string; text: string; x: number; y: number }[] = [];
  for (const e of els) {
    if (e.type === "text") {
      const t = (e.text || "").trim();
      if (!t) continue;
      if (e.containerId) {
        textByContainer[e.containerId] = (
          (textByContainer[e.containerId] || "") + " " + t
        ).trim();
      } else {
        standaloneText.push({ id: e.id, text: t, x: e.x || 0, y: e.y || 0 });
      }
    }
  }

  // 2) Components = shapes, labeled by their bound text (or nearest standalone).
  const byId: Record<string, DiagramComponent> = {};
  const components: DiagramComponent[] = [];
  for (const e of els) {
    if (SHAPE_TYPES.has(e.type)) {
      let label = textByContainer[e.id] || "";
      if (!label) {
        // nearest standalone text inside the shape's bounds
        const near = standaloneText.find(
          (t) =>
            t.x >= (e.x || 0) - 10 &&
            t.x <= (e.x || 0) + (e.width || 0) + 10 &&
            t.y >= (e.y || 0) - 10 &&
            t.y <= (e.y || 0) + (e.height || 0) + 10
        );
        label = near?.text || "";
      }
      const comp = { id: e.id, label: label || "(unlabeled)", shape: e.type };
      byId[e.id] = comp;
      components.push(comp);
    }
  }

  const labelFor = (elId: string | undefined): string => {
    if (!elId) return "?";
    return byId[elId]?.label || "?";
  };

  // 3) Edges = arrows/lines with bindings (direction = start -> end).
  const edges: DiagramEdge[] = [];
  for (const e of els) {
    if (e.type === "arrow" || e.type === "line") {
      const from = labelFor(e.startBinding?.elementId);
      const to = labelFor(e.endBinding?.elementId);
      if (from === "?" && to === "?") continue; // unbound decoration
      const label = textByContainer[e.id] || undefined;
      edges.push({ from, to, label });
    }
  }

  // 4) Loose labels = standalone text not used as a component label.
  const usedText = new Set(components.map((c) => c.label));
  const loose = standaloneText
    .map((t) => t.text)
    .filter((t) => !usedText.has(t));

  return {
    components,
    edges,
    loose_labels: loose,
    counts: { components: components.length, edges: edges.length },
  };
}

/** Compact text form of the graph for prompts / debugging. */
export function diagramToText(m: DiagramModel): string {
  if (!m || m.counts.components === 0) return "(empty diagram)";
  const comps = m.components.map((c) => c.label).join(", ");
  const edges = m.edges
    .map((e) => `${e.from} → ${e.to}${e.label ? ` [${e.label}]` : ""}`)
    .join("; ");
  const loose = m.loose_labels.length
    ? ` | notes: ${m.loose_labels.join(", ")}`
    : "";
  return `Components: ${comps}\nConnections: ${edges || "(none)"}${loose}`;
}
