# --- Production console image: build the Angular app, serve static via nginx ---
#
# Stage 1 compiles the SPA; stage 2 ships only the static bundle behind nginx,
# so the runtime image carries no Node toolchain. The browser still calls the
# API directly at the host-published port (see src/environments/environment.ts),
# so nginx only needs to serve files + do SPA fallback — no reverse proxy.

# --- build ---
FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# --- runtime ---
FROM nginx:1.27-alpine AS runtime
LABEL org.opencontainers.image.source="https://github.com/gridatek/agentforge"
LABEL org.opencontainers.image.description="AgentForge admin console"
# The `application` builder emits browser assets under dist/<project>/browser.
COPY --from=build /app/dist/console/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
