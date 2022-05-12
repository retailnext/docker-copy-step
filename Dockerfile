FROM debian:11-slim AS build
RUN apt-get update \
&& apt-get install --no-install-suggests --no-install-recommends --yes \
ca-certificates \
gcc \
libpython3-dev \
python3-venv \
wget \
&& python3 -m venv /venv \
&& /venv/bin/pip install --upgrade pip setuptools wheel

FROM build AS download
WORKDIR /usr/local/bin

FROM download as download-docker-credential-ecr-login
ARG ECR_LOGIN_VERSION=0.6.0
ARG ECR_LOGIN_SHA256=af805202cb5d627dde2e6d4be1f519b195fd5a3a35ddc88d5010b4a4e5a98dd8
RUN wget -O docker-credential-ecr-login \
https://amazon-ecr-credential-helper-releases.s3.us-east-2.amazonaws.com/${ECR_LOGIN_VERSION}/linux-amd64/docker-credential-ecr-login \
&& echo "$ECR_LOGIN_SHA256 docker-credential-ecr-login" | sha256sum --check --quiet --strict \
&& chmod 0755 docker-credential-ecr-login

FROM download as download-docker-credential-gcr
ARG GCR_VERSION=2.1.3
ARG GCR_SHA256=1cb318aee93f1d8a7a9632e5d7f518950a5baf7218e28cc1917ff9a82a54d391
RUN wget -O docker-credential-gcr.tar.gz \
https://github.com/GoogleCloudPlatform/docker-credential-gcr/releases/download/v${GCR_VERSION}/docker-credential-gcr_linux_amd64-${GCR_VERSION}.tar.gz \
&& echo "$GCR_SHA256  docker-credential-gcr.tar.gz" | sha256sum --check --strict \
&& tar xzvf docker-credential-gcr.tar.gz \
&& rm docker-credential-gcr.tar.gz

FROM download as download-regctl
ARG REGCTL_VERSION=0.4.2
ARG REGCTL_SHA256=bc7407180999acbd8c724237403802394f899714fc9fd7678d0e54072140ea5c
RUN wget -O regctl \
https://github.com/regclient/regclient/releases/download/v${REGCTL_VERSION}/regctl-linux-amd64 \
&& echo "$REGCTL_SHA256  regctl" | sha256sum --check --quiet --strict \
&& chmod 0755 regctl

FROM build AS build-venv
COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

FROM gcr.io/distroless/python3-debian11:debug
COPY --from=download-docker-credential-ecr-login /usr/local/bin/docker-credential-ecr-login /usr/local/bin/
COPY --from=download-docker-credential-gcr /usr/local/bin/docker-credential-gcr /usr/local/bin/
COPY --from=download-regctl /usr/local/bin/regctl /usr/local/bin/
COPY --from=build-venv /venv /venv

WORKDIR /app
COPY copy-image.py /app/copy-image.py
ENTRYPOINT ["/venv/bin/python3", "/app/copy-image.py"]
