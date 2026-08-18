FROM node:22.22.0-bookworm-slim AS build

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /app/
COPY services/pi-agent/package.json /app/services/pi-agent/package.json

RUN corepack enable && pnpm install --frozen-lockfile --prod=false --filter @docpilot/pi-agent...

COPY services/pi-agent/tsconfig.json /app/services/pi-agent/tsconfig.json
COPY services/pi-agent/src /app/services/pi-agent/src
RUN pnpm --filter @docpilot/pi-agent build

FROM node:22.22.0-bookworm-slim
WORKDIR /app/services/pi-agent
ENV NODE_ENV=production
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/services/pi-agent/node_modules /app/services/pi-agent/node_modules
COPY --from=build /app/services/pi-agent/package.json ./package.json
COPY --from=build /app/services/pi-agent/dist ./dist
EXPOSE 8787
CMD ["node", "dist/server.js"]
