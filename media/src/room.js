import { createRouter, createWebRtcTransport } from "./mediasoup.js";
import { FrameSampler } from "./frameSampler.js";

/**
 * One Room per interview session. Holds the mediasoup router, the client's
 * WebRTC transports/producers, and a FrameSampler per video producer so the AI
 * interviewer can "see" the camera and screen.
 */
export class Room {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.router = null;
    this.transports = new Map(); // transportId -> transport
    this.producers = new Map(); // producerId -> producer
    this.samplers = new Map(); // producerId -> FrameSampler
  }

  async init() {
    this.router = await createRouter();
  }

  async createTransport() {
    const { transport, params } = await createWebRtcTransport(this.router);
    this.transports.set(transport.id, transport);
    transport.on("dtlsstatechange", (s) => {
      if (s === "closed") transport.close();
    });
    return params;
  }

  async connectTransport(transportId, dtlsParameters) {
    const t = this.transports.get(transportId);
    if (!t) throw new Error("transport not found");
    await t.connect({ dtlsParameters });
  }

  /**
   * appData.source is "camera" | "screen" | "mic". Video producers get a
   * FrameSampler attached so their frames flow to the Core API.
   */
  async produce(transportId, kind, rtpParameters, appData = {}) {
    const t = this.transports.get(transportId);
    if (!t) throw new Error("transport not found");
    const producer = await t.produce({ kind, rtpParameters, appData });
    this.producers.set(producer.id, producer);

    if (kind === "video") {
      const source = appData.source === "screen" ? "screen" : "camera";
      const sampler = new FrameSampler({
        router: this.router,
        producer,
        sessionId: this.sessionId,
        source,
      });
      await sampler.start();
      this.samplers.set(producer.id, sampler);
    }

    producer.on("transportclose", () => this._closeProducer(producer.id));
    return { id: producer.id };
  }

  async _closeProducer(producerId) {
    const sampler = this.samplers.get(producerId);
    if (sampler) {
      await sampler.close();
      this.samplers.delete(producerId);
    }
    this.producers.delete(producerId);
  }

  async close() {
    for (const s of this.samplers.values()) await s.close();
    for (const t of this.transports.values()) t.close();
    this.router?.close();
  }
}
