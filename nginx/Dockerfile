FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
RUN echo 'add_header X-Leyzen-Server nginx;' >> /etc/nginx/conf.d/default.conf

