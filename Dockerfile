FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY results/public/ ./public/results/
RUN npm run build

FROM node:24-alpine AS runtime
ENV NODE_ENV=production PORT=8080
WORKDIR /app
COPY --from=build --chown=node:node /app/dist ./dist
COPY --chown=node:node deploy/server.mjs ./server.mjs
USER node
EXPOSE 8080
CMD ["node", "server.mjs"]
