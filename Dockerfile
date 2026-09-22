FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    PORT=8080 \
    XRAY_MODE=auto \
    XRAY_BASE_PORT=10000 \
    XRAY_REALITY_PORT=8443 \
    SINGBOX_MODE=auto

WORKDIR /app

# ---------------------------------------------------------------- protocol core
# Xray-core serves everything this panel offers over TCP: VLESS / VMess / Trojan /
# Shadowsocks and Reality, over WebSocket, XHTTP, gRPC, HTTPUpgrade and raw TCP.
#
# It is fetched with Python's own urllib, so no curl/tar is needed. To bump the version,
# change the tag in the URL below.
#
# Every step is a separate, independently guarded layer (`|| echo WARNING`), so a blocked or
# moved download can never fail the build - the panel simply reports the core as missing in
# Settings -> Xray-core and keeps working with its built-in relay.
#
# sing-box (Hysteria2 / TUIC / ShadowTLS) is intentionally not installed: Railway only
# exposes TCP, so those UDP protocols cannot be reached from here, and it cost ~30 MB of
# every build. Add it back with the three lines in the comment at the end of this file if
# you run this image somewhere that allows UDP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    || echo "WARNING: could not install ca-certificates"

RUN python -c "import io,os,urllib.request,zipfile;os.makedirs('/tmp/sbx',exist_ok=True);d=urllib.request.urlopen('https://github.com/XTLS/Xray-core/releases/download/v26.3.27/Xray-linux-64.zip',timeout=180).read();zipfile.ZipFile(io.BytesIO(d)).extractall('/tmp/sbx');print('xray downloaded',len(d)//1024,'KB')" \
    || echo "WARNING: Xray-core download failed (VMess/Shadowsocks/xhttp/gRPC need an external core)"

RUN install -m 0755 /tmp/sbx/xray /usr/local/bin/xray \
    && /usr/local/bin/xray version \
    || echo "WARNING: Xray-core not installed"

# ---------------------------------------------------------------- python deps
# Requirements live on their own layer, so changing application code never re-installs them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------- app
COPY . .
# /data is the Railway volume mount; create it so the default path always exists.
RUN mkdir -p /data

EXPOSE 8080

# Liveness is probed by the platform (railway.json -> deploy.healthcheckPath: /health).
CMD ["python", "main.py"]

# ---------------------------------------------------------------- optional: sing-box
# Uncomment to also ship the QUIC/UDP engine (needs a host that allows UDP):
#
# RUN python -c "import io,os,tarfile,urllib.request;os.makedirs('/tmp/sb',exist_ok=True);d=urllib.request.urlopen('https://github.com/SagerNet/sing-box/releases/download/v1.14.1/sing-box-1.14.1-linux-amd64.tar.gz',timeout=240).read();tf=tarfile.open(fileobj=io.BytesIO(d));names=[n for n in tf.getnames() if n.split('/')[-1]=='sing-box' and not n.endswith('/')];open('/tmp/sb/sing-box','wb').write(tf.extractfile(names[0]).read())" \
#     || echo "WARNING: sing-box download failed"
# RUN install -m 0755 /tmp/sb/sing-box /usr/local/bin/sing-box || echo "WARNING: sing-box not installed"
