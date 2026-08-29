import * as mediasoup from "mediasoup";
import { config, mediaCodecs } from "./config.js";

let worker;

export async function getWorker() {
  if (worker) return worker;
  worker = await mediasoup.createWorker({
    rtcMinPort: config.rtcMinPort,
    rtcMaxPort: config.rtcMaxPort,
    logLevel: "warn",
  });
  worker.on("died", () => {
    console.error("[mediasoup] worker died, exiting");
    process.exit(1);
  });
  return worker;
}

export async function createRouter() {
  const w = await getWorker();
  return w.createRouter({ mediaCodecs });
}

export async function createWebRtcTransport(router) {
  const transport = await router.createWebRtcTransport({
    listenIps: [{ ip: "0.0.0.0", announcedIp: config.announcedIp }],
    enableUdp: true,
    enableTcp: true,
    preferUdp: true,
  });
  return {
    transport,
    params: {
      id: transport.id,
      iceParameters: transport.iceParameters,
      iceCandidates: transport.iceCandidates,
      dtlsParameters: transport.dtlsParameters,
    },
  };
}
