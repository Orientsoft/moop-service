FROM alpine:3.9

RUN apk --update add git less openssh bash curl&& \
    rm -rf /var/lib/apt/lists/* && \
    rm /var/cache/apk/*
