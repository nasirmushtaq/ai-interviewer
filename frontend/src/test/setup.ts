/**
 * Test harness: mock the browser Speech APIs so we can drive the voice hook
 * deterministically and assert its behavior (start/stop lifecycle, buffering,
 * transcript flow).
 */
import { vi } from "vitest";

// ---- Mock SpeechRecognition ----
export class MockSpeechRecognition {
  lang = "";
  continuous = false;
  interimResults = false;
  onresult: ((e: any) => void) | null = null;
  onerror: ((e: any) => void) | null = null;
  onend: (() => void) | null = null;
  onstart: (() => void) | null = null;

  running = false;
  startCount = 0;
  stopCount = 0;

  static instances: MockSpeechRecognition[] = [];

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start() {
    // Chrome throws if start() is called while already running.
    if (this.running) {
      throw new DOMException("recognition already started", "InvalidStateError");
    }
    this.running = true;
    this.startCount++;
    this.onstart?.();
  }

  stop() {
    this.stopCount++;
    if (this.running) {
      this.running = false;
      // Chrome fires onend asynchronously after stop.
      queueMicrotask(() => this.onend?.());
    }
  }

  // Test helper: simulate the user finishing a spoken phrase.
  emitFinal(text: string) {
    this.onresult?.({
      resultIndex: 0,
      results: [
        Object.assign([{ transcript: text }], { isFinal: true }),
      ],
    });
  }

  emitInterim(text: string) {
    this.onresult?.({
      resultIndex: 0,
      results: [
        Object.assign([{ transcript: text }], { isFinal: false }),
      ],
    });
  }

  emitError(error: string) {
    this.onerror?.({ error });
  }
}

// ---- Mock speechSynthesis ----
class MockUtterance {
  text: string;
  voice: any = null;
  rate = 1;
  pitch = 1;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}

const mockSynth = {
  speak(u: any) {
    // Resolve speech immediately in tests.
    queueMicrotask(() => {
      u.onstart?.();
      u.onend?.();
    });
  },
  cancel() {},
  resume() {},
  getVoices() {
    return [{ lang: "en-US", name: "Google US English" }];
  },
  onvoiceschanged: null as any,
};

export function installSpeechMocks() {
  MockSpeechRecognition.instances = [];
  (window as any).SpeechRecognition = MockSpeechRecognition;
  (window as any).webkitSpeechRecognition = MockSpeechRecognition;
  (window as any).speechSynthesis = mockSynth;
  (window as any).SpeechSynthesisUtterance = MockUtterance;
  // Grant mic by default.
  (navigator as any).mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: () => {} }],
    }),
  };
}

export function currentRecognition(): MockSpeechRecognition {
  const list = MockSpeechRecognition.instances;
  return list[list.length - 1];
}
