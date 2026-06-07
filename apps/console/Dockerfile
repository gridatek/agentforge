# Dev-mode container for the Angular console (ng serve).
# For production, build with `ng build` and serve dist/ behind nginx.
FROM node:20-slim

WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .

EXPOSE 4200
CMD ["npm", "start"]
