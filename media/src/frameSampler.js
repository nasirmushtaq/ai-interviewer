import { spawn } from "node:child_process";
import net from "node:net";
import { fetch } from "undici";
import { config } from "./config.js";

/**
 * FrameSampler pipes a single video producer's RTP into ffmpeg and periodically
 * grabs a downscaled JPEG frame, which it POSTs to the Core API for GPT-4o
 * vision analysis. `source` is "camera" or "screen".
 */
export class FrameSampler {
  constructor({ router, producer, sessionId, source }) {
    this.router = router;
    this.producer = producer;
    this.sessionId = sessionId;
    this.source = source;
    this.transport = null;
    this.consumer = null;
    this.ffmpeg = null;
    this.timer = null;
    this.latestJpeg = null;
    this.closed = false;
  }

  async _freeUdpPort() {
    // Ask the OS for a free UDP port by binding ephemerally.
    return await new Promise((resolve, reject) => {
      const sock = net.createServer();
      sock.listen(0, "127.0.0.1", () => {
        const { port } = sock.address();
        sock.close(() => resolve(port));
      });
      sock.on("error", reject);
    });
  }

  async start() {
    const rtpPort = await this._freeUdpPort();

    // PlainTransport to send this producer's RTP to local ffmpeg.
    this.transport = await this.router.createPlainTransport({
      listenIp: { ip: "127.0.0.1" },
      rtcpMux: true,
      comedia: false,
    });
    await this.transport.connect({ ip: "127.0.0.1", port: rtpPort });

    this.consumer = await this.transport.consume({
      producerId: this.producer.id,
      rtpCapabilities: this.router.rtpCapabilities,
      paused: false,
    });

    const { payloadType } = this.consumer.rtpParameters.codecs[0];
    const ssrc = this.consumer.rtpParameters.encodings[0].ssrc;

    // Build a minimal SDP describing the incoming VP8 RTP stream for ffmpeg.
    const sdp = [
      "v=0",
      "o=- 0 0 IN IP4 127.0.0.1",
      "s=linguacall",
      "c=IN IP4 127.0.0.1",
      "t=0 0",
      `m=video ${rtpPort} RTP/AVP ${payloadType}`,
      `a=rtpmap:${payloadType} VP8/90000`,
      `a=ssrc:${ssrc} cname:linguacall`,
      "a=recvonly",
    ].join("\n");

    // ffmpeg reads the SDP over stdin, decodes VP8, and writes single-frame
    // JPEGs to stdout at ~1 fps, scaled down. We keep only the latest frame.
    this.ffmpeg = spawn(
      "ffmpeg",
      [
        "-loglevel", "error",
        "-protocol_whitelist", "pipe,udp,rtp",
        "-f", "sdp",
        "-i", "pipe:0",
        "-vf", `fps=1,scale=${config.frameWidth}:-1`,
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1",
      ],
      { stdio: ["pipe", "pipe", "inherit"] }
    );
    this.ffmpeg.stdin.write(sdp);
    this.ffmpeg.stdin.end();

    // Reassemble JPEGs from the MJPEG byte stream (SOI 0xFFD8 .. EOI 0xFFD9).
    let buf = Buffer.alloc(0);
    this.ffmpeg.stdout.on("data", (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      let start = buf.indexOf(Buffer.from([0xff, 0xd8]));
      let end = buf.indexOf(Buffer.from([0xff, 0xd9]), start + 2);
      while (start !== -1 && end !== -1) {
        this.latestJpeg = buf.subarray(start, end + 2);
        buf = buf.subarray(end + 2);
        start = buf.indexOf(Buffer.from([0xff, 0xd8]));
        end = buf.indexOf(Buffer.from([0xff, 0xd9]), start + 2);
      }
    });
    this.ffmpeg.on("error", (e) =>
      console.error(`[sampler:${this.source}] ffmpeg error`, e.message)
    );

    // Periodically ship the latest frame to the Core API for analysis.
    this.timer = setInterval(
      () => this._sendLatest(),
      config.frameSampleIntervalMs
    );
    console.log(
      `[sampler:${this.source}] started for session ${this.sessionId}`
    );
  }

  async _sendLatest() {
    if (this.closed || !this.latestJpeg) return;
    const dataUrl =
      "data:image/jpeg;base64," + this.latestJpeg.toString("base64");
    try {
      const res = await fetch(
        `${config.coreApiUrl}/api/sessions/${this.sessionId}/frames`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Media-Token": config.mediaServiceToken,
          },
          body: JSON.stringify({ source: this.source, image: dataUrl }),
        }
      );
      if (!res.ok) {
        console.warn(
          `[sampler:${this.source}] core API ${res.status}: ${await res.text()}`
        );
      }
    } catch (e) {
      console.warn(`[sampler:${this.source}] send failed:`, e.message);
    }
  }

  async close() {
    this.closed = true;
    clearInterval(this.timer);
    try {
      this.ffmpeg?.kill("SIGKILL");
    } catch {}
    try {
      await this.consumer?.close();
    } catch {}
    try {
      await this.transport?.close();
    } catch {}
  }
}
