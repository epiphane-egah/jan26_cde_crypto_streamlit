# ---------- BUILD ----------
    FROM node:22-alpine AS build

    WORKDIR /app
    
    COPY package-lock.json /app/
    COPY package.json /app/
    RUN npm ci
    
    COPY . .
    
    # ARG VITE_API_URL
    ENV VITE_API_URL=https://jan26-cde-crypto-api-975242104567.europe-west1.run.app/api
    
    RUN npm run build
    
    
    # ---------- PROD ----------
    FROM nginx:alpine
    
    COPY --from=build /app/dist /usr/share/nginx/html
    
    COPY nginx.conf /etc/nginx/conf.d/default.conf
    
    EXPOSE 8501
    
    CMD ["nginx", "-g", "daemon off;"]