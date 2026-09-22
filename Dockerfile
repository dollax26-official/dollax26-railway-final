FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8080 \
    XRAY_MODE=auto \
    XRAY_BASE_PORT=10000 \
    XRAY_REALITY_PORT=8443 \
    SINGBOX_MODE=auto \
    SINGBOX_BASE_PORT=11000

WORKDIR /app

# ---------------------------------------------------------------- protocol cores
# Two engines are bundled so every protocol the panel offers has a real implementation:
#
#   * Xray-core -> VLESS / VMess / Trojan / Shadowsocks (+ Reality) over WebSocket, XHTTP,
#                  gRPC, HTTPUpgrade, TCP. The panel drives it: it keeps the public HTTPS
#                  port for the WebSocket protocols and gives every Reality inbound its own
#                  raw TCP port (Reality cannot pass through a TLS-terminating proxy).
#   * sing-box  -> Hysteria2 / TUIC / ShadowTLS (QUIC/UDP family). Railway exposes TCP, so
#                  those become reachable when the same image runs where UDP is allowed.
#
# EVERY download is optional: each step runs inside `( ... ) || echo WARNING` so a blocked
# or moved release asset can never fail the image build. The panel detects what is present
# and reports it in Settings -> Xray-core.
ARG XRAY_VERSION=v26.3.27
ARG SINGBOX_VERSION=1.14.1
RUN set -eux; \
    ( apt-get update \
      && apt-get install -y --no-install-recommends ca-certificates curl tar \
      && rm -rf /var/lib/apt/lists/* ) \
      || echo "WARNING: could not install curl/tar - skipping the bundled cores"; \
    ( mkdir -p /tmp/sbx && curl -fsSL --retry 3 -o /tmp/xray.zip \
        "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" \
      && python -c "import zipfile; zipfile.ZipFile('/tmp/xray.zip').extractall('/tmp/sbx')" \
      && install -m 0755 /tmp/sbx/xray /usr/local/bin/xray \
      && /usr/local/bin/xray version ) \
      || echo "WARNING: Xray-core ${XRAY_VERSION} not installed - VMess/Shadowsocks/xhttp/gRPC need an external core"; \
    ( mkdir -p /tmp/sb && curl -fsSL --retry 3 -o /tmp/sb.tgz \
        "https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-linux-amd64.tar.gz" \
      && tar -xzf /tmp/sb.tgz -C /tmp/sb \
      && install -m 0755 "$(find /tmp/sb -type f -name sing-box | head -n1)" /usr/local/bin/sing-box \
      && /usr/local/bin/sing-box version ) \
      || echo "WARNING: sing-box ${SINGBOX_VERSION} not installed - Hysteria2/TUIC/ShadowTLS stay link-only"; \
    rm -rf /tmp/sbx /tmp/sb /tmp/xray.zip /tmp/sb.tgz; \
    echo "cores present:"; ls -l /usr/local/bin/xray /usr/local/bin/sing-box 2>/dev/null || true

# ---------------------------------------------------------------- app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /data is the Railway volume mount; create it so the default path always exists.
RUN mkdir -p /data

EXPOSE 8080

# Liveness is probed by the platform (railway.json -> deploy.healthcheckPath: /health).
# No Docker-level HEALTHCHECK on purpose: a duplicated probe can mark a healthy
# container unhealthy and make the proxy answer "Application failed to respond".

# No shell, no quoting, no globs: python resolves $PORT itself (see main.py __main__) and
# starts the bundled Xray-core from the panel's lifespan hook.
CMD ["python", "main.py"]
