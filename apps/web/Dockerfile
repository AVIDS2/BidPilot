FROM node:22-alpine AS build

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json /app/apps/web/package.json
COPY apps/web/index.html /app/apps/web/index.html
COPY apps/web/vite.config.ts /app/apps/web/vite.config.ts
COPY apps/web/tsconfig.json /app/apps/web/tsconfig.json
COPY apps/web/components.json /app/apps/web/components.json
COPY apps/web/vitest.setup.ts /app/apps/web/vitest.setup.ts
COPY apps/web/playwright.config.ts /app/apps/web/playwright.config.ts
COPY apps/web/public /app/apps/web/public
COPY apps/web/src /app/apps/web/src

RUN corepack enable && corepack prepare pnpm@10.0.0 --activate
RUN pnpm install --frozen-lockfile

ARG VITE_API_URL=http://localhost:8000
ARG VITE_TURNSTILE_SITE_KEY
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_TURNSTILE_SITE_KEY=${VITE_TURNSTILE_SITE_KEY}

RUN pnpm --filter @docpilot/web build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
