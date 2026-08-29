# ---- Web (Vite build -> nginx static) ----
FROM node:20-bookworm-slim AS build
WORKDIR /app

# VITE_API_URL is baked at build time (Vite inlines import.meta.env). Pass with
#   docker build --build-arg VITE_API_URL=https://api.example.com
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ >/dev/null 2>&1 || exit 1
