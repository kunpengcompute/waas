FROM python:3.9.9-slim as builder

ARG PIP_PROXY
#ARG PIP_PROXY="http://username:password@http.example.com:8080"

ARG PACKAGES="numpy pandas pmdarima statsmodels"

RUN if [ -n "${PIP_PROXY}" ]; then \
        pip install ${PACKAGES} --no-cache-dir --proxy ${PIP_PROXY}; \
    else \
        pip install ${PACKAGES} --no-cache-dir; \
    fi

WORKDIR /app

COPY src/waasbooster/*.py ./

CMD ["python", "cpu_booster.py"]