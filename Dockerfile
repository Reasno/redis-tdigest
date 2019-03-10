FROM redis:latest as builder

ENV LIBDIR /usr/lib/redis/modules
ENV DEPS "python python-setuptools python-pip wget unzip build-essential"
# Set up a build environment
RUN set -ex;\
    deps="$DEPS";\
    apt-get update; \
	apt-get install -y --no-install-recommends $deps;\
    pip install rmtest; 

# Build the source
ADD . /TDIGEST
WORKDIR /TDIGEST
RUN set -ex;\
    make clean; \
    deps="$DEPS";\
    make all -j 4;
# Package the runner
FROM redis:latest
ENV LIBDIR /usr/lib/redis/modules
WORKDIR /data
RUN set -ex;\
    mkdir -p "$LIBDIR";
COPY --from=builder /TDIGEST/tdigest.so  "$LIBDIR"

CMD ["redis-server", "--loadmodule", "/usr/lib/redis/modules/tdigest.so"]