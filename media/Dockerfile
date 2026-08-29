# ---- Media SFU (Node + mediasoup) ----
# mediasoup needs a build toolchain + python at install time; slim keeps runtime lean.
FROM node:20-bookworm-slim

ENV NODE_ENV=production

WORKDIR /app

# Build deps for mediasoup's native worker; ffmpeg for frame sampling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 build-essential ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install --omit=dev

COPY . .

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 4000
# RTC media ports (align with RTC_MIN_PORT/RTC_MAX_PORT in env).
EXPOSE 40000-40100/udp

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:4000/health || exit 1

CMD ["node", "src/server.js"]
