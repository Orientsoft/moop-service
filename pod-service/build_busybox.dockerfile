FROM progrium/busybox

RUN \
    mv /lib/libgcc_s.so.1 /lib/libgcc_s.so.1.bak && \
    opkg-install curl bash git
