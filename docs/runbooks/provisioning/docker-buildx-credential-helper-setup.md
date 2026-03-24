# Docker Buildx and Credential Helper Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-10

## Purpose

Restore a working local Docker CLI path for Nova service-image builds on Ubuntu
or WSL when:

- `docker buildx` is missing or shadowed by broken plugin symlinks
- `docker build` or BuildKit fails because `docker-credential-desktop.exe`
  is configured but unavailable

This guide is for local operator and developer workstations. It does not change
the release-environment contract, which is already defined in
`buildspecs/buildspec-release.yml`.

Documentation authority:
[`../release/README.md#canonical-documentation-authority-chain`](../release/README.md#canonical-documentation-authority-chain).

## When to Use This

Use this guide when any of the following fail locally:

```bash
docker buildx version
DOCKER_BUILDKIT=1 docker build -f apps/nova_file_api_service/Dockerfile .
DOCKER_BUILDKIT=1 docker buildx build --load -f apps/nova_file_api_service/Dockerfile .
```

Common failure signatures:

- `docker-credential-desktop.exe: executable file not found in $PATH`
- `BuildKit is enabled but the buildx component is missing or broken`
- plugin metadata errors under `/usr/local/lib/docker/cli-plugins`

## Preconditions

1. Ubuntu or WSL shell access with `sudo`
2. Docker CLI already installed
3. Local Nova checkout available

## Step 1: Inspect Current State

Run:

```bash
cat /etc/os-release
uname -m
docker --version
docker buildx version

ls -la /usr/local/lib/docker/cli-plugins 2>/dev/null || true
ls -la ~/.docker/cli-plugins 2>/dev/null || true
cat ~/.docker/config.json 2>/dev/null || true
```

Healthy local signals:

- `docker --version` succeeds
- `docker buildx version` succeeds
- a working `docker-buildx` binary exists either in
  `/usr/local/lib/docker/cli-plugins` or `~/.docker/cli-plugins`
- `~/.docker/config.json` does not reference an unavailable credential helper

## Step 2: Repair Plugin Paths

If `docker buildx version` fails or `/usr/local/lib/docker/cli-plugins` is
populated by broken Docker Desktop symlinks, promote the working user-local
plugins into the system path:

```bash
sudo install -d -m 0755 /usr/local/lib/docker/cli-plugins

sudo rm -f /usr/local/lib/docker/cli-plugins/docker-buildx
sudo rm -f /usr/local/lib/docker/cli-plugins/docker-compose

sudo install -m 0755 ~/.docker/cli-plugins/docker-buildx /usr/local/lib/docker/cli-plugins/docker-buildx
sudo install -m 0755 ~/.docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
```

If `~/.docker/cli-plugins/docker-buildx` does not exist, install a fresh
release binary. This guide targets x86_64 (amd64); for arm64, use
`linux-arm64` in the URL suffix.

```bash
BUILDX_VERSION=v0.30.1
ARCH=$(uname -m)
case "$ARCH" in
  x86_64) BUILDX_SUFFIX=linux-amd64 ;;
  aarch64|arm64) BUILDX_SUFFIX=linux-arm64 ;;
  *) echo "Unsupported arch: $ARCH"; exit 1 ;;
esac

sudo install -d -m 0755 /usr/local/lib/docker/cli-plugins
sudo curl -SL \
  "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.${BUILDX_SUFFIX}" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
```

## Step 3: Repair Broken Credential Helper Configuration

If `~/.docker/config.json` contains:

```json
{
  "credsStore": "desktop.exe"
}
```

and the matching helper is not available in WSL, remove the broken
`credsStore` entry and keep the rest of the config:

```bash
cp ~/.docker/config.json ~/.docker/config.json.bak.$(date +%Y%m%d%H%M%S)

python3 - <<'PY'
import json
from pathlib import Path

config_path = Path.home() / ".docker" / "config.json"
config = json.loads(config_path.read_text())
config.pop("credsStore", None)
config_path.write_text(json.dumps(config, indent=2) + "\n")
print(f"updated {config_path}")
PY
```

Do not remove `auths` entries unless they are also incorrect.

## Step 4: Re-Verify Docker and Buildx

Run:

```bash
docker buildx version
docker buildx inspect --bootstrap
docker compose version
```

These must succeed before trying Nova image builds again.

## Step 5: Re-Authenticate Registries If Needed

If removing `credsStore` invalidates cached credentials, log back in.

Docker Hub:

```bash
docker login
```

ECR example (replace `${AWS_REGION}` and `${AWS_ACCOUNT_ID}` with your values):

```bash
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin \
    "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

## Step 6: Verify Nova Service Image Builds

From the repo root (replace `<NOVA_REPO_ROOT>` with your local clone path):

```bash
cd <NOVA_REPO_ROOT>

DOCKER_BUILDKIT=1 docker buildx build --load \
  -f apps/nova_file_api_service/Dockerfile \
  -t nova-file-api:test .
```

Optional runtime smoke checks:

```bash
docker run --rm -p 8050:8050 nova-file-api:test
curl -fsS http://127.0.0.1:8050/v1/health/live
```

## Step 7: Verify Repo-Native Gates

After Docker is fixed, re-run the focused repo checks:

```bash
source .venv/bin/activate && uv lock --check
source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests/test_runtime_security_reliability_gates.py
```

## Notes

- Nova release images remain owned by `apps/*` Dockerfiles.
- Nova service images now target the Python `3.13-slim` baseline and use pinned
  `uv` for reproducible dependency installation.
- Production service containers remain single-process `uvicorn` containers with
  explicit proxy flags.
- BuildKit is now part of the Nova release-image contract; local Docker must be
  able to satisfy that path for workstation image verification.

## References

- Docker buildx install docs:
  <https://docs.docker.com/build/building/multi-platform/#install-buildx>
- Docker build best practices:
  <https://docs.docker.com/build/building/best-practices/>
- [SPEC-0000](../../architecture/spec/SPEC-0000-http-api-contract.md)
- `../../../buildspecs/buildspec-release.yml`
