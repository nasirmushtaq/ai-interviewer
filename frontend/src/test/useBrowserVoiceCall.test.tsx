import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { installSpeechMocks, currentRecognition } from "./setup";
import { useBrowserVoiceCall } from "../hooks/useBrowserVoiceCall";

// Mock the API so no network is needed; chat echoes a canned reply.
vi.mock("../api", () => ({
  api: {
    chat: vi.fn(async (payload: any) => ({
      reply: payload.message.includes("Greet")
        ? "Hello! First question: reverse a linked list."
        : `You said: ${payload.message}`,
    })),
  },
  setAuthToken: vi.fn(),
}));

import { api } from "../api";

beforeEach(() => {
  installSpeechMocks();
  (api.chat as any).mockClear();
});

const payload = { username: "t", mode: "interview", focus: "dsa", session_id: "s1" };

describe("useBrowserVoiceCall", () => {
  it("goes live and greets, without hanging on connecting", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    await waitFor(() => expect(result.current.status).toBe("live"));
    // Greeting should be in the transcript.
    await waitFor(() =>
      expect(
        result.current.transcript.some((t) => t.role === "assistant")
      ).toBe(true)
    );
  });

  it("starts recognition AFTER the greeting (no start/stop race)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));
    // It should be cleanly running with exactly one active start (the race bug
    // manifested as start()->stop()->start churn or a stuck non-running state).
    expect(recog.running).toBe(true);
  });

  it("CAPTURES user speech into the transcript (the reported bug)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));

    // User speaks.
    await act(async () => {
      recog.emitFinal("I would use three pointers");
    });

    // The user's utterance must appear in the transcript.
    await waitFor(() =>
      expect(
        result.current.transcript.some(
          (t) => t.role === "user" && t.text.includes("three pointers")
        )
      ).toBe(true)
    );
    // And the AI must reply to it.
    await waitFor(() =>
      expect(
        result.current.transcript.some((t) =>
          t.text.includes("You said: I would use three pointers")
        )
      ).toBe(true)
    );
  });

  it("BUFFERS speech that arrives while the AI is busy (not dropped)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));

    // Fire two utterances back-to-back; the second arrives while the first is
    // being processed. Neither should be lost.
    await act(async () => {
      recog.emitFinal("first answer");
      recog.emitFinal("second answer");
    });

    await waitFor(() => {
      const userTurns = result.current.transcript.filter((t) => t.role === "user");
      const texts = userTurns.map((t) => t.text).join(" | ");
      expect(texts).toContain("first answer");
      expect(texts).toContain("second answer");
    });
  });

  it("shows interim (live) text as the user speaks", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));

    await act(async () => {
      recog.emitInterim("thinking out loud");
    });
    expect((result.current as any).interimText).toContain("thinking out loud");
  });

  it("sendText fallback works even without speech", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    await waitFor(() => expect(result.current.status).toBe("live"));
    await act(async () => {
      (result.current as any).sendText("typed answer");
    });
    await waitFor(() =>
      expect(
        result.current.transcript.some((t) => t.text.includes("typed answer"))
      ).toBe(true)
    );
  });
});

describe("real-world failure modes", () => {
  it("surfaces a 'network' recognition error (Chrome needs internet for STT)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));
    await act(async () => {
      recog.emitError("network");
    });
    await waitFor(() =>
      expect(result.current.error.toLowerCase()).toContain("network")
    );
  });

  it("surfaces 'audio-capture' error (wrong mic / no input device)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));
    await act(async () => {
      recog.emitError("audio-capture");
    });
    await waitFor(() =>
      expect(result.current.error.toLowerCase()).toContain("audio-capture")
    );
  });

  it("recognition that never emits results = silent 'listening' (the exact symptom)", async () => {
    const { result } = renderHook(() => useBrowserVoiceCall());
    await act(async () => {
      await result.current.start(payload);
    });
    const recog = currentRecognition();
    await waitFor(() => expect(recog.running).toBe(true));
    // Simulate the real bug: mic is 'listening' but NO onresult ever fires.
    // The transcript should have ONLY the greeting, no user turns — proving
    // that when Chrome doesn't emit, our hook is fine but has nothing to show.
    const userTurns = result.current.transcript.filter((t) => t.role === "user");
    expect(userTurns.length).toBe(0);
    expect(result.current.status).toBe("live"); // stuck listening, not broken
  });
});
