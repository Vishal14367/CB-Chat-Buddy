# ── Frontend Dockerfile (multi-stage) ─────────────────────────────────────────
# Stage 1: BUILD — installs deps and compiles Next.js with standalone output
# Stage 2: RUNNER — lean production image (~200 MB vs ~1 GB)

# ── Stage 1: Builder ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps (cached layer — only re-runs if package files change)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

# NEXT_PUBLIC_API_URL is a client-side env var baked into the JS bundle at build time.
# Pass the public backend URL here (e.g. https://api.yourdomain.com/api).
# Coolify: set NEXT_PUBLIC_API_URL in the Environment Variables UI for this service.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ── Stage 2: Runner ────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy the standalone server bundle and static assets
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

# Next.js standalone output creates a self-contained server.js at the root
CMD ["node", "server.js"]
