import "dotenv/config";

export const config = {
  port: Number(process.env.PORT || 4000),
  coreApiUrl: process.env.CORE_API_URL || "http://localhost:8000",
  mediaServiceToken: process.env.MEDIA_SERVICE_TOKEN || "dev-media-token",
  announcedIp: process.env.MEDIASOUP_ANNOUNCED_IP || "127.0.0.1",
  rtcMinPort: Number(process.env.RTC_MIN_PORT || 40000),
  rtcMaxPort: Number(process.env.RTC_MAX_PORT || 40100),
  frameSampleIntervalMs: Number(process.env.FRAME_SAMPLE_INTERVAL_MS || 6000),
  frameWidth: Number(process.env.FRAME_WIDTH || 640),
};

// Codecs the SFU will negotiate. VP8 keeps server-side frame extraction simple.
export const mediaCodecs = [
  {
    kind: "audio",
    mimeType: "audio/opus",
    clockRate: 48000,
    channels: 2,
  },
  {
    kind: "video",
    mimeType: "video/VP8",
    clockRate: 90000,
    parameters: { "x-google-start-bitrate": 1000 },
  },
];
