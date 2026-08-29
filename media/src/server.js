import http from "node:http";
import express from "express";
import cors from "cors";
import { WebSocketServer } from "ws";
import { config } from "./config.js";
import { getWorker } from "./mediasoup.js";
import { Room } from "./room.js";

const app = express();
app.use(cors());
app.use(express.json());

const rooms = new Map(); // sessionId -> Room

app.get("/health", (_req, res) =>
  res.json({ ok: true, service: "linguacall-media", rooms: rooms.size })
);

const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/ws" });

async function getRoom(sessionId) {
  let room = rooms.get(sessionId);
  if (!room) {
    room = new Room(sessionId);
    await room.init();
    rooms.set(sessionId, room);
  }
  return room;
}

/**
 * Signaling protocol (JSON over WebSocket). Each message: { id, action, data }.
 * The server replies with { id, ok, data } or { id, ok:false, error }.
 *
 * Actions:
 *  - join            { sessionId }                         -> { rtpCapabilities }
 *  - createTransport { direction:"send" }                  -> transport params
 *  - connectTransport{ transportId, dtlsParameters }       -> { connected:true }
 *  - produce         { transportId, kind, rtpParameters, appData:{source} }
 *                                                          -> { id }
 */
wss.on("connection", (ws) => {
  let room = null;

  const reply = (id, ok, payload) =>
    ws.send(
      JSON.stringify(
        ok ? { id, ok: true, data: payload } : { id, ok: false, error: payload }
      )
    );

  ws.on("message", async (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    const { id, action, data = {} } = msg;
    try {
      switch (action) {
        case "join": {
          room = await getRoom(data.sessionId);
          reply(id, true, { rtpCapabilities: room.router.rtpCapabilities });
          break;
        }
        case "createTransport": {
          if (!room) throw new Error("join first");
          const params = await room.createTransport();
          reply(id, true, params);
          break;
        }
        case "connectTransport": {
          if (!room) throw new Error("join first");
          await room.connectTransport(data.transportId, data.dtlsParameters);
          reply(id, true, { connected: true });
          break;
        }
        case "produce": {
          if (!room) throw new Error("join first");
          const result = await room.produce(
            data.transportId,
            data.kind,
            data.rtpParameters,
            data.appData || {}
          );
          reply(id, true, result);
          break;
        }
        default:
          reply(id, false, `unknown action: ${action}`);
      }
    } catch (e) {
      console.error("[ws] error:", e.message);
      reply(id, false, e.message);
    }
  });

  ws.on("close", () => {
    // Keep the room alive briefly so a reconnect/grade can still read it;
    // real cleanup happens when the session ends. For the prototype we close
    // rooms with no producers left after a delay.
    setTimeout(async () => {
      if (room && room.producers.size === 0) {
        rooms.delete(room.sessionId);
        await room.close();
      }
    }, 30000);
  });
});

(async () => {
  await getWorker(); // fail fast if mediasoup can't start
  server.listen(config.port, () =>
    console.log(
      `[linguacall-media] SFU on :${config.port} (announcedIp=${config.announcedIp}) -> core ${config.coreApiUrl}`
    )
  );
})();
