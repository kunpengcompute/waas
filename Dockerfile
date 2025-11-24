FROM python:3.9.9-slim as builder

ARG PIP_PROXY

ARG PIP_MIRROR
ARG PIP_TRUST_HOST

WORKDIR /app

COPY requirements.txt ./

ARG PIP_BASE_CMD="pip install -r requirements.txt --no-cache-dir"

RUN install_cmd="${PIP_BASE_CMD}"; \
    if [ -n "${PIP_PROXY}" ]; then \
        install_cmd="${install_cmd} --proxy ${PIP_PROXY}"; \
    fi; \
    if [ -n "${PIP_MIRROR}" ]; then \
        install_cmd="${install_cmd} -i ${PIP_MIRROR} --trusted-host ${PIP_TRUST_HOST}"; \
    fi; \
    echo "install command: ${install_cmd}"; \
    eval "${install_cmd}"

COPY src/waasbooster/*.py ./

CMD ["python", "waas_booster.py"]