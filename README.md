# ⚠️ Archived

We no longer use this.

We instead run pproxy in a separate container using the image built by
[retailnext/pproxy](https://github.com/retailnext/pproxy), then just use
upstream [regctl](https://github.com/regclient/regclient) docker images as
a discrete Cloud Build step with the environment variables set to direct
its traffic towards the pproxy container.

# docker-copy-step

This Google Cloud Build step image uses
[regctl](https://github.com/regclient/regclient) to copy Docker images
between repositories without loading them into a local Docker daemon.

It configures credential helpers for ECR, GCR, and Google Artifact Registry
repos. It can use [pproxy](https://github.com/qwj/python-proxy) to tunnel
access to one or both of the repositories.

## Usage

There is currently no public image, so you'll need to build and put this
into a repo that your Cloud Build job has access to.

In the following example, the image is copied from Artifact Registry to ECR
in AWS China. The connection to ECR is tunneled through two SSH bastion hosts.

```yaml
  - id: push-to-china
    waitFor:
      - image
    name: us-docker.pkg.dev/.../docker-copy-step
    env:
      - AWS_ACCESS_KEY_ID=AKIAxxxxx
      - SSH_USER=myuser
      - SSH_HOSTS=1.2.3.4,10.20.30.40
      - no_proxy=us-central1-docker.pkg.dev,oauth2.googleapis.com
    args:
      - us-central1-docker.pkg.dev/my-source-image/...:tag
      - nnnnnnnnn.dkr.ecr.cn-northwest-1.amazonaws.com.cn/my-destimage:tag
    secretEnv:
      - AWS_SECRET_ACCESS_KEY
      - SSH_KEY
```

### Advanced Usage: `REMAP_ENV_`

To work around the annoying limitation in Google Cloud Build where secrets are
defined for the entire build and thus the environment variable name for them
is forced to be the same for all steps in the build, this tool can remap
environment variables before interpreting them or passing them to child
processes like the credential helpers.

In the following example, we copy to ECR in the US with no ssh proxy, and to
ECR in China through bastion hosts. Because we can't have two different
secrets both named `AWS_SECRET_ACCESS_KEY`, we define them with unique names
then have this step remap them.

```yaml
  - id: push-to-china
    waitFor:
      - image
    name: us-docker.pkg.dev/.../docker-copy-step
    env:
      - no_proxy=us-central1-docker.pkg.dev,oauth2.googleapis.com
      - REMAP_ENV_AWS_ACCESS_KEY_ID=CN_DEPLOY_AWS_ACCESS_KEY_ID
      - REMAP_ENV_AWS_SECRET_ACCESS_KEY=CN_DEPLOY_AWS_SECRET_ACCESS_KEY
      - SSH_USER=myuser
    args:
      - us-central1-docker.pkg.dev/my-source-image/...:tag
      - nnnnnnnnn.dkr.ecr.cn-northwest-1.amazonaws.com.cn/my-destimage:tag
    secretEnv:
      - CN_DEPLOY_AWS_ACCESS_KEY_ID
      - CN_DEPLOY_AWS_SECRET_ACCESS_KEY
      - SSH_KEY
      - SSH_HOSTS
  - id: push-to-us
    waitFor:
      - image
    name: us-docker.pkg.dev/.../docker-copy-step
    env:
      - REMAP_ENV_AWS_ACCESS_KEY_ID=US_DEPLOY_AWS_ACCESS_KEY_ID
      - REMAP_ENV_AWS_SECRET_ACCESS_KEY=US_DEPLOY_AWS_SECRET_ACCESS_KEY
    args:
      - us-central1-docker.pkg.dev/my-source-image/...:tag
      - mmmmmmmm.dkr.ecr.us-west-2.amazonaws.com/my-destimage:tag
    secretEnv:
      - US_DEPLOY_AWS_ACCESS_KEY_ID
      - US_DEPLOY_AWS_SECRET_ACCESS_KEY
```

## Project Status: Works For Us

We use this, but maintaining it is not a priority for us.

This is written in Python solely because pproxy is written in Python.

Areas needing improvement:

* Improve documentation and add code comments.
* Support more credential providers.
* Handle logging better. In particular, prefix messages from child processes.
* CI/CD to automatically update with new versions of dependencies.
* Rewrite in go?

## Contributing

Contributions considered, but be aware that this is mostly just something we
needed. It's public because there's no reason anyone else should have to waste
an afternoon (or more) building something similar.

This project is licensed under the [Apache License, Version 2.0](LICENSE).

Please include a `Signed-off-by` in all commits, per
[Developer Certificate of Origin version 1.1](DCO).
