FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
COPY scripts/copy-pdf-worker.cjs scripts/copy-pdf-worker.cjs

RUN npm ci

COPY . .

ARG INTERNAL_API_URL=http://backend:8000/api
ENV INTERNAL_API_URL=${INTERNAL_API_URL}
ENV NODE_ENV=production

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]