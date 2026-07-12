FROM node:22-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
COPY server/package.json server/package.json
COPY webview-ui/package.json webview-ui/package.json
RUN npm ci

COPY . .
RUN npm run asyncapi:generate \
    && npm run check-types \
    && node esbuild.js --production \
    && npm run build:webview

FROM node:22-slim AS runtime

ENV NODE_ENV=production

RUN groupadd --system sellerbuddy \
    && useradd --system --gid sellerbuddy --home-dir /app sellerbuddy \
    && mkdir -p /app \
    && chown sellerbuddy:sellerbuddy /app

WORKDIR /app
COPY --from=builder --chown=sellerbuddy:sellerbuddy /app/dist ./dist
COPY --from=builder --chown=sellerbuddy:sellerbuddy /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force

USER sellerbuddy
EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3100/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]

CMD ["node", "dist/cli.js", "--host", "0.0.0.0", "--port", "3100"]
