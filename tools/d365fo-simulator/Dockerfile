# syntax=docker/dockerfile:1.7
# Local Dynamics 365 F&O simulator (test double for Future Mirror's connector). See README.md.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 SIM_CERT_DIR=/certs
WORKDIR /sim
COPY requirements.txt .
# Optional corporate/proxy CA (BuildKit secret "extra_ca"); never persisted in the image.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install -r requirements.txt
COPY d365fo_sim ./d365fo_sim
EXPOSE 8443
HEALTHCHECK --interval=10s --timeout=5s --retries=10 CMD python -c "import ssl,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('https://localhost:8443/health', context=ssl._create_unverified_context()).status==200 else 1)"
CMD ["python", "-m", "d365fo_sim.run"]
