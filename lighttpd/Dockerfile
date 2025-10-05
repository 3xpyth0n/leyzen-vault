FROM alpine:3.18
RUN apk add --no-cache lighttpd
COPY index.html /var/www/localhost/htdocs/index.html
RUN echo 'setenv.add-response-header  = ( "X-Leyzen-Server" => "lighttpd" )' >> /etc/lighttpd/lighttpd.conf
CMD ["lighttpd", "-D", "-f", "/etc/lighttpd/lighttpd.conf"]

