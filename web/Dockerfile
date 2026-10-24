# Production image of the web client: the static build served by the stack's own Nginx
# (infra/nginx/default.conf serves it at "/" next to /api and /ws). Built by deploy.yml.
FROM node:24-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@10.28.0
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# Vite reads these at build time only (docs/DEPLOYMENT.md); changing them needs a rebuild.
ARG VITE_DATA_SOURCE=demo
# relative: the API is on the page's own origin (same nginx), so it follows http/https
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_SITE_URL=
ENV VITE_DATA_SOURCE=$VITE_DATA_SOURCE VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_SITE_URL=$VITE_SITE_URL
RUN pnpm exec vite build

FROM nginx:1.27-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html
