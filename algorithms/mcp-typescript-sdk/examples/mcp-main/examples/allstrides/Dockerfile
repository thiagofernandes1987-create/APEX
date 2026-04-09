# Stage 1: Build Frontend
FROM node:22-alpine as frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Build Server
FROM node:22-alpine as server-build
WORKDIR /app/server
COPY server/package*.json ./
RUN npm install
COPY server/ .
RUN npm run build

# Stage 3: Production Runtime
FROM node:22-alpine
WORKDIR /app

# Copy built frontend
COPY --from=frontend-build /app/frontend/build /app/frontend/build

# Copy built server
COPY --from=server-build /app/server/dist /app/server/dist
COPY --from=server-build /app/server/package*.json /app/server/

# Install production dependencies for server
WORKDIR /app/server
RUN npm install --production

# Environment
ENV PORT=8080
ENV NODE_ENV=production

CMD ["node", "dist/index.js"]