FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci

COPY apps/web ./apps/web

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NODE_ENV=production

RUN npm run build:web

EXPOSE 3000

CMD ["npm", "--workspace", "@nodesh/web", "run", "start"]
