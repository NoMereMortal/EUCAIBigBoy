FROM node:23-alpine AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./
RUN npm ci

# Development image with full dependencies including devDependencies
FROM base AS development
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./
# Install all dependencies including devDependencies for development
RUN npm ci --include=dev

# Copy all source files
COPY . .

# Expose port
EXPOSE 3000

# Set environment
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1

# Default command for development
CMD ["npm", "run", "dev"]

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build the Next.js application with ESLint errors as warnings
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_OPTIONS="--experimental-vm-modules --no-warnings"
# Build with --no-lint to skip ESLint check or with ESLINT_STRICT=false to treat errors as warnings
RUN npm run build -- --no-lint || npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

# Set NODE_ENV to production by default, but allow override via environment variables
ENV NODE_ENV=production

# Install bash and curl for our scripts and health check
RUN apk add --no-cache bash curl

# Create a non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Add AWS SDK packages and core Node.js modules that are needed for scripts
WORKDIR /app
RUN npm init -y && \
    npm install --production @aws-sdk/client-ssm @aws-sdk/client-secrets-manager \
    && npm install --production http path url fs \
    && chmod -R 755 /app/node_modules \
    && chown -R nextjs:nodejs /app/node_modules

# Copy built application - core files that should always exist
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/scripts ./scripts

# Prepare directories
RUN mkdir -p /app/out /app/.next /app/.next/static

# Create a script to handle conditional copying
RUN echo '#!/bin/sh' > /tmp/copy-build.sh && \
    echo 'if [ -d "/build/out" ]; then cp -r /build/out/. /app/out/; fi' >> /tmp/copy-build.sh && \
    echo 'if [ -d "/build/.next" ]; then cp -r /build/.next/. /app/.next/; fi' >> /tmp/copy-build.sh && \
    echo 'if [ -d "/build/.next/standalone" ]; then cp -r /build/.next/standalone/. /app/; fi' >> /tmp/copy-build.sh && \
    echo 'if [ -d "/build/.next/static" ]; then cp -r /build/.next/static/. /app/.next/static/; fi' >> /tmp/copy-build.sh && \
    chmod +x /tmp/copy-build.sh

# Copy the build files using the script
COPY --from=builder /app /build
RUN /tmp/copy-build.sh && rm -rf /build /tmp/copy-build.sh

# Set executable permissions on the scripts
RUN chmod +x ./scripts/startup.sh ./scripts/fetch-ssm.cjs ./scripts/create-dev-config.cjs ./scripts/static-server.cjs

# Create directory for runtime configuration
RUN mkdir -p /app/public && chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Use startup script instead of directly running server.js
CMD ["./scripts/startup.sh"]
