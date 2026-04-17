FROM nginx:1.27-alpine

ENV PORT=8080

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY index.html /usr/share/nginx/html/index.html
COPY assets /usr/share/nginx/html/assets
COPY projects /usr/share/nginx/html/projects
COPY 标准计划书PDF /usr/share/nginx/html/标准计划书PDF

EXPOSE 8080
