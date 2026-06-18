# syntax=docker/dockerfile:1
# Next.js 15 admin dashboard. Build from the frontend/ directory:
#   docker build -t ai-recruiter-frontend frontend/

# ---- deps: install node_modules from the lockfile -------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# Prefer the reproducible lockfile install; fall back to `npm install` when the
# committed lockfile is out of sync (e.g. missing optional platform deps).
RUN npm ci || npm install

# ---- builder: produce the standalone server bundle ------------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined at build time. NEXT_PUBLIC_VOICE_URL is the
# voice-service origin the BROWSER hits, so it must be the host-reachable URL
# (e.g. http://localhost:7860), not the internal compose hostname.
ARG NEXT_PUBLIC_VOICE_URL=http://localhost:7860
ENV NEXT_PUBLIC_VOICE_URL=${NEXT_PUBLIC_VOICE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---- runner: minimal runtime image ---------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# Standalone output = server.js + traced node_modules; static assets ship alongside.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# BACKEND_URL + ADMIN_API_TOKEN are server-only and injected at runtime by compose;
# the same-origin /api/admin proxy reads them to reach FastAPI.
CMD ["node", "server.js"]
