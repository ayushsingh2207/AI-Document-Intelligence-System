# ==============================================================================
# AI Document Intelligence System - Frontend Dockerfile
# Multi-stage production build for Next.js App Router (Node 20 Alpine)
# ==============================================================================

# Stage 1: Dependency resolution and production build
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies needed during build
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source code and config
COPY . .

# Build argument for backend API URL (baked into client bundle during next build)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NODE_ENV=production

# Compile production Next.js application
RUN npm run build

# Stage 2: Minimal runtime image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Copy necessary files from builder
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

CMD ["npm", "run", "start"]
