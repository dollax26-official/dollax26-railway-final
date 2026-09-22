FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8080 \
    XRAY_MODE=auto \
    XRAY_BASE_PORT=10000 \
    SINGBOX_MODE=auto \
    SINGBOX_BASE_PORT=11000

WORKDIR /app

# ---------------------------------------------------------------- protocol cores
# Two engines are bundled so every protocol the panel offers has a real implementation:
#
#   * Xray-core  → VLESS / VMess / Trojan / Shadowsocks and the TCP transports
#                  (WebSocket, XHTTP, gRPC, HTTPUpgrade, TCP+header). This is the one the
#                  panel drives automatically: it keeps the single public port and pipes
#                  each connection into a local ws inbound on 127.0.0.1:10000+i.
#   * sing-box   → Hysteria2 / TUIC / ShadowTLS (QUIC/UDP family). Railway only exposes
#                  TCP, so those inbounds become reachable when the same image runs on a
#                  host with UDP; the panel still generates their links/configs.
#
# Both downloads are deliberately non-fatal: if GitHub is unreachable at build time the
# image still builds and the panel falls back to its built-in VLESS/Trojan-over-WebSocket
# relay (set XRAY_MODE=off to skip the core entirely).
ARG XRAY_VERSION=v26.3.27
ARG SINGBOX_VERSION=1.14.1
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl tar; \
    rm -rf /var/lib/apt/lists/*; \
    # ---- Xray-core ----
    mkdir -p /usr/local/share/xray; \
    if curl -fsSL --retry 3 -o /tmp/xray.zip \
        "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip"; \
    then \
        python -c "import zipfile; zipfile.ZipFile('/tmp/xray.zip').extractall('/usr/local/share/xray')"; \
        install -m 0755 /usr/local/share/xray/xray /usr/local/bin/xray; \
        rm -f /tmp/xray.zip; \
        xray version || true; \
    else \
        echo "WARNING: could not download Xray-core ${XRAY_VERSION}; VMess/Shadowsocks/xhttp/gRPC will need an external core"; \
    fi; \
    # ---- sing-box ----
    if curl -fsSL --retry 3 -o /tmp/singbox.tgz \
        "https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-linux-amd64.tar.gz"; \
    then \
        mkdir -p /tmp/sb; tar -xzf /tmp/singbox.tgz -C /tmp/sb; \
        install -m 0755 "$(find /tmp/sb -type f -name sing-box | head -n1)" /usr/local/bin/sing-box; \
        rm -rf /tmp/sb /tmp/singbox.tgz; \
        sing-box version || true; \
    else \
        echo "WARNING: could not download sing-box ${SINGBOX_VERSION}; Hysteria2/TUIC/ShadowTLS stay link-only"; \
    fi

# ---------------------------------------------------------------- app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/health').read()"

# No shell, no quoting, no globs: python resolves $PORT itself (see main.py __main__) and
# starts the bundled Xray-core from the panel's lifespan hook.
CMD ["python", "main.py"]
