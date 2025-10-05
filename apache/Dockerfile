FROM httpd:alpine
COPY index.html /usr/local/apache2/htdocs/index.html
COPY header.conf /usr/local/apache2/conf/extra/header.conf
RUN echo "Include conf/extra/header.conf" >> /usr/local/apache2/conf/httpd.conf

