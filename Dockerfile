# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    PORT=8080 \
    XRAY_MODE=auto \
    XRAY_BASE_PORT=10000 \
    XRAY_REALITY_PORT=8443 \
    SINGBOX_MODE=auto \
    SINGBOX_BASE_PORT=11000

WORKDIR /app

# ---------------------------------------------------------------- protocol core(s)
# Xray-core is what actually serves this panel (VLESS/VMess/Trojan/Shadowsocks + Reality,
# over WebSocket / XHTTP / gRPC / HTTPUpgrade / TCP). It is fetched with Python's own urllib,
# so the image only needs `ca-certificates` from apt - no curl/tar layer, no wasted seconds.
#
# sing-box (Hysteria2 / TUIC / ShadowTLS) is opt-in: Railway exposes TCP only, so those
# protocols cannot be reached from this container anyway and fetching it costs ~30 MB per
# build. Enable it with the build arg INSTALL_SINGBOX=1 if you run this image where UDP works.
#
# Every step is wrapped in `( ... ) || echo WARNING`, so a blocked or moved download can
# never fail the build. The panel reports what it found in Settings -> Xray-core.
ARG XRAY_VERSION=v26.3.27
ARG SINGBOX_VERSION=1.14.1
ARG INSTALL_SINGBOX=0
RUN set -eux; \
    ( apt-get update \
      && apt-get install -y --no-install-recommends ca-certificates \
      && rm -rf /var/lib/apt/lists/* ) \
      || echo "WARNING: ca-certificates unavailable"; \
    ( python -c "import io,os,urllib.request,zipfile,sys;os.makedirs('/tmp/sbx',exist_ok=True);d=urllib.request.urlopen(sys.argv[1],timeout=180).read();zipfile.ZipFile(io.BytesIO(d)).extractall('/tmp/sbx');print('xray downloaded',len(d)//1024,'KB')" \
        "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" \
      && install -m 0755 /tmp/sbx/xray /usr/local/bin/xray \
      && /usr/local/bin/xray version ) \
      || echo "WARNING: Xray-core not installed - VMess/Shadowsocks/xhttp/gRPC need an external core"; \
    if [ "${INSTALL_SINGBOX}" = "1" ]; then \
      ( python -c "import io,os,tarfile,urllib.request,sys;os.makedirs('/tmp/sb',exist_ok=True);d=urllib.request.urlopen(sys.argv[1],timeout=240).read();tf=tarfile.open(fileobj=io.BytesIO(d));names=[n for n in tf.getnames() if n.split('/')[-1]=='sing-box' and not n.endswith('/')];open('/tmp/sb/sing-box','wb').write(tf.extractfile(names[0]).read());print('sing-box downloaded',len(d)//1024,'KB')" \
          "https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-linux-amd64.tar.gz" \
        && install -m 0755 /tmp/sb/sing-box /usr/local/bin/sing-box \
        && /usr/local/bin/sing-box version ) \
        || echo "WARNING: sing-box not installed - Hysteria2/TUIC/ShadowTLS stay link-only"; \
    fi; \
    rm -rf /tmp/sbx /tmp/sb; \
    ls -l /usr/local/bin/xray /usr/local/bin/sing-box 2>/dev/null || true

# ---------------------------------------------------------------- python deps
# Requirements on their own layer (code changes never re-install them) plus a pip cache
# mount, so a redeploy reuses the wheels instead of downloading them again.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# ---------------------------------------------------------------- app
COPY . .
# pre-compile once at build time: slightly faster first request on a cold container
RUN python -m compileall -q /app > /dev/null 2>&1 || true; mkdir -p /data

EXPOSE 8080

# Liveness is probed by the platform (railway.json -> deploy.healthcheckPath: /health).
CMD ["python", "main.py"]
