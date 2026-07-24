ARG NODE_IMAGE=registry.access.redhat.com/ubi9/nodejs-22:latest
ARG BUILD_IMAGE=registry.access.redhat.com/ubi9/ubi:latest
ARG PYTHON_IMAGE=registry.access.redhat.com/ubi9/python-312:latest

FROM ${NODE_IMAGE} AS frontend
WORKDIR /opt/app-root/src
COPY --chown=1001:0 frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY --chown=1001:0 frontend/ ./
RUN npm test \
    && npm run build

FROM ${BUILD_IMAGE} AS stockfish
ARG STOCKFISH_TAG=sf_18
USER 0
RUN dnf install -y gcc-c++ make tar gzip findutils \
    && dnf clean all
WORKDIR /usr/src
RUN curl --fail --location --retry 3 \
      "https://github.com/official-stockfish/Stockfish/archive/refs/tags/${STOCKFISH_TAG}.tar.gz" \
      --output stockfish.tar.gz \
    && mkdir stockfish \
    && tar --extract --gzip --file stockfish.tar.gz --strip-components=1 --directory stockfish \
    && cd stockfish/src \
    && case "$(uname -m)" in \
         x86_64) make -j2 build ARCH=x86-64-sse41-popcnt ;; \
         aarch64) make -j2 build ARCH=armv8 ;; \
         *) make -j2 build ARCH=general-64 ;; \
       esac \
    && install -D -m 0755 stockfish /out/stockfish \
    && mkdir -p /out/source \
    && cp /usr/src/stockfish.tar.gz "/out/source/stockfish-${STOCKFISH_TAG}.tar.gz" \
    && cp /usr/src/stockfish/Copying.txt /out/source/Copying.txt \
    && cp /usr/src/stockfish/AUTHORS /out/source/AUTHORS \
    && find /usr/src/stockfish/src -maxdepth 1 -name '*.nnue' \
       -exec cp '{}' /out/source/ ';'

FROM ${PYTHON_IMAGE} AS runtime
ARG STOCKFISH_TAG=sf_18
ARG APP_VERSION=0.1.0
ARG VCS_REF=unknown
USER 0
WORKDIR /opt/app
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir . \
    && mkdir -p /opt/app/frontend /usr/share/licenses/stockfish /usr/src/stockfish /tmp/chess-coach \
    && chgrp -R 0 /opt/app /tmp/chess-coach \
    && chmod -R g=u /opt/app /tmp/chess-coach
COPY --from=frontend /opt/app-root/src/dist ./frontend/dist
COPY --from=stockfish /out/stockfish /usr/local/bin/stockfish
COPY --from=stockfish /out/source /usr/src/stockfish
RUN cp /usr/src/stockfish/Copying.txt /usr/share/licenses/stockfish/COPYING \
    && cp /usr/src/stockfish/AUTHORS /usr/share/licenses/stockfish/AUTHORS \
    && printf '%s\n' "${STOCKFISH_TAG}" > /usr/share/licenses/stockfish/VERSION \
    && chmod -R a=rX /usr/src/stockfish /usr/share/licenses/stockfish /opt/app/frontend

ENV CHESS_STATIC_DIR=/opt/app/frontend/dist \
    CHESS_STOCKFISH_PATH=/usr/local/bin/stockfish \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TMPDIR=/tmp/chess-coach
LABEL org.opencontainers.image.title="Chess Coach" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/official-stockfish/Stockfish"

EXPOSE 8080
ENTRYPOINT ["python", "-m", "app.cli"]
CMD ["web"]

FROM runtime AS test
USER 0
COPY tests ./tests
RUN pip install --no-cache-dir '.[dev]' \
    && python -m pytest \
    && ruff check app tests

FROM runtime AS final
