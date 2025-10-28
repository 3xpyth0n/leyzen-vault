# syntax=docker/dockerfile:1
FROM alpine:3.19 AS filebrowser

ARG FILEBROWSER_VERSION=2.44.2
ARG FILEBROWSER_ARCHIVE_NAME="linux-amd64-filebrowser.tar.gz"
ARG FILEBROWSER_CHECKSUMS_NAME="filebrowser_${FILEBROWSER_VERSION}_checksums.txt"
ARG FILEBROWSER_DOWNLOAD_URL="https://github.com/filebrowser/filebrowser/releases/download/v${FILEBROWSER_VERSION}/${FILEBROWSER_ARCHIVE_NAME}"
ARG FILEBROWSER_CHECKSUMS_URL="https://github.com/filebrowser/filebrowser/releases/download/v${FILEBROWSER_VERSION}/${FILEBROWSER_CHECKSUMS_NAME}"

RUN apk add --no-cache ca-certificates curl tar su-exec && \
    mkdir -p /usr/local/bin && \
    curl -fsSL "$FILEBROWSER_DOWNLOAD_URL" -o /tmp/filebrowser.tar.gz && \
    FILEBROWSER_SHA256="$(curl -fsSL "$FILEBROWSER_CHECKSUMS_URL" | awk -v file="$FILEBROWSER_ARCHIVE_NAME" '$2 == file {print $1}')" && \
    [ -n "$FILEBROWSER_SHA256" ] || { \
        echo "Failed to retrieve checksum for $FILEBROWSER_ARCHIVE_NAME"; \
        exit 1; \
    } && \
    echo "${FILEBROWSER_SHA256}  /tmp/filebrowser.tar.gz" | sha256sum -c - || { \
        echo "Checksum verification failed"; \
        exit 1; \
    } && \
    tar -xzf /tmp/filebrowser.tar.gz -C /usr/local/bin filebrowser && \
    chmod +x /usr/local/bin/filebrowser && \
    rm -f /tmp/filebrowser.tar.gz && \
    addgroup -S filebrowser && \
    adduser -S -H -D -G filebrowser filebrowser && \
    mkdir -p /config /database /srv && \
    chown -R filebrowser:filebrowser /config /database /srv

COPY ./entrypoint.sh /usr/local/bin/filebrowser-entrypoint.sh
RUN chmod +x /usr/local/bin/filebrowser-entrypoint.sh

ENV FILEBROWSER_BIN=/usr/local/bin/filebrowser

EXPOSE 80
VOLUME ["/config", "/database", "/srv"]

ENTRYPOINT ["/usr/local/bin/filebrowser-entrypoint.sh"]
CMD ["--root", "/srv", "--address", "0.0.0.0", "--port", "80"]
