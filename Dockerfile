FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8080

WORKDIR /app

# install deps first so the layer caches
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# The image must render /login, /static/* and /info/<token> even if the panel was
# never opened, so a healthcheck is enough to catch a broken start.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/health').read()"

# No shell, no quoting, no globs: python resolves $PORT itself (see main.py __main__).
# Railway injects PORT (8080 by convention); the service's public-networking target
# port must be the same number.
CMD ["python", "main.py"]
