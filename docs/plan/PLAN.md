# PLAN.md - aws-file-transfer-api (and refactors across aws-dash-s3-file-handler + pca-analysis-dash)

> Scope: This plan creates a new canonical backend repository `aws-file-transfer-api`, migrates all backend/API logic out of `aws-dash-s3-file-handler`, dedupes/refactors the Dash handler package to become a UI + Dash integration wrapper, and cleans up `pca-analysis-dash` to consume the final packages correctly (no duplicated presign endpoints or S3 logic).
>
> Repository locations (local paths):
>
> - container-craft: `~/repos/work/infra-stack/container-craft`
> - aws-file-transfer-api: `~/repos/work/infra-stack/aws-file-transfer-api`
> - aws-dash-s3-file-handler: `~/repos/work/infra-stack/aws-dash-s3-file-handler`
> - pca-analysis-dash (Dash app): `~/repos/work/pca-analysis-dash/dash-pca`
>
> Must-have properties
>
> - [x] Direct-to-S3 uploads/downloads via presigned URLs; multipart for large files
> - [x] Align with container-craft FILE_TRANSFER_* contract and defaults
> - [x] Transfer Acceleration supported (dev+prod)
> - [x] App-side upload caps configurable per app (PCA app: 200 MB)
> - [x] Robust typing, validation, test coverage, and CI quality gates
> - [x] The backend API layer becomes reusable across Dash apps, and also deployable as a standalone FastAPI service for non-Python clients when needed
>
> How Codex should execute this plan
>
> 1) Implement sequentially in PR-sized chunks (see "PR breakdown" sections).
> 2) After each PR: run `uv run ruff format .`, `uv run ruff check .`, `uv run mypy .`, `uv run pytest`.
> 3) Tick checkboxes as completed and append brief notes under "Progress Log".
> 4) If a task is changed, update this PLAN.md (do not drift from the contract).

---

## 0. Inputs, current state, and invariants (ground truth)

### 0.1 Canonical container-craft contract (must remain compatible)

When `file_transfer_enabled: "true"`, container-craft injects these env vars (names + defaults are normative):

- FILE_TRANSFER_BUCKET
- FILE_TRANSFER_UPLOAD_PREFIX (default: uploads/)
- FILE_TRANSFER_EXPORT_PREFIX (default: exports/)
- FILE_TRANSFER_TMP_PREFIX (default: tmp/)
- FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS (default: 900)
- FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS (default: 900)
- FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES (default: 104857600 / 100 MiB)
- FILE_TRANSFER_PART_SIZE_BYTES (default: 134217728 / 128 MiB)
- FILE_TRANSFER_MAX_CONCURRENCY (default: 4)
- FILE_TRANSFER_USE_ACCELERATE_ENDPOINT (true|false)

Primary references (container-craft repo, local paths):

- `~/repos/work/infra-stack/container-craft/infra/file_transfer/s3.yml`
- `~/repos/work/infra-stack/container-craft/infra/ecs/service.yml`
- `~/repos/work/infra-stack/container-craft/src/container-craft/settings/service.yml`
- `~/repos/work/infra-stack/container-craft/templates/3m.yml`
- `~/repos/work/infra-stack/container-craft/docs/architecture/file-transfer.md`
- `~/repos/work/infra-stack/container-craft/docs/how-to/file-transfer.md`

### 0.2 Existing aws-dash-s3-file-handler capabilities we must preserve (and relocate)

The current `aws-dash-s3-file-handler` repo already contains:

- Typed env config + upload policy + auth policy
- S3 client factory (accelerate-aware)
- Pydantic request/response models
- A service layer implementing initiate/sign-parts/complete/abort/presign-download
- Flask blueprint endpoints with stable error envelope
- Optional FastAPI adapter
- Dash UI integration + packaged uploader JS (assets/file_transfer.js) that does multipart and updates dcc.Store

Migration rule: Everything listed above except the Dash UI integration and packaged assets must be moved into the new canonical backend repo.

Primary references (aws-dash-s3-file-handler repo, local paths):

- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/config.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/models.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/s3_client.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/service.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/flask_integration.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/fastapi_integration.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/dash_integration.py`
- `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/assets/file_transfer.js`

### 0.3 PCA app constraints

- PCA app upload cap: 200 MB (enforced at presign/initiate)
- PCA app supports CSV + Excel only
- PCA app must stop using any duplicated file transfer endpoint code and instead import/compose from the final packages.

Primary references (pca-analysis-dash repo, local paths):

- `~/repos/work/pca-analysis-dash/dash-pca/src/api/file_transfer.py`
- `~/repos/work/pca-analysis-dash/dash-pca/src/services/file_transfer_service.py`
- `~/repos/work/pca-analysis-dash/dash-pca/configs/service/dev.yml`
- `~/repos/work/pca-analysis-dash/dash-pca/configs/service/prod.yml`

### 0.4 AWS multipart invariants to enforce

- Part numbers: 1..10,000
- Part size: 5 MiB .. 5 GiB (last part may be smaller)
- Transfer Acceleration requires correct bucket naming constraints (no dots) and generating presigns against accelerate endpoint when enabled.

AWS references:

- Multipart upload limits (S3 User Guide): <https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html>
- Multipart overview (S3 User Guide): <https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html>
- Transfer Acceleration: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html>
- Transfer Acceleration examples and CLI/SDK config note: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration-examples.html>

---

## 1. Architectural decision framework (Tier 2) - final decisions must be >= 9.0/10

### 1.1 Options considered

Option A - Status quo: keep backend + UI together in aws-dash-s3-file-handler

- Pros: minimal changes
- Cons: backend logic lives inside a Dash-branded package; harder to reuse for non-Dash apps; increases coupling and slows future multi-language adoption; duplicates grow per app repo.

Option B - Chosen: create aws-file-transfer-api as canonical backend library + FastAPI app; keep aws-dash-s3-file-handler as UI wrapper

- Pros: backend is canonical, reusable, testable; Dash handler becomes thin; PCA app imports cleanly; backend can be deployed standalone (FastAPI) or embedded (Flask blueprint) depending on needs; reduces long-term drift.
- Cons: requires careful backwards compatibility (re-exports) and repo refactor.

Option C - Standalone service only (Dash becomes pure HTTP client, no embedded blueprint)

- Pros: best for multi-language clients immediately
- Cons: introduces cross-origin/CORS/auth complexity for Dash browser flows, and requires infra routing decisions that are not currently first-class in container-craft’s host-header model.

### 1.2 Decision score table (must be >= 9.0)

| Option | Complexity (40%) | Perf (30%) | Alignment (30%) | Total |
| :--- | :---: | :---: | :---: | :---: |
| B - Canonical backend repo + UI wrapper | 10 (4.0) | 9 (2.7) | 10 (3.0) | 9.7 |
| C - Standalone service only | 6 (2.4) | 9 (2.7) | 9 (2.7) | 7.8 |
| A - Status quo | 7 (2.8) | 8 (2.4) | 6 (1.8) | 7.0 |

Rationale: Option B provides the cleanest separation (backend vs UI), minimal friction for Dash apps (embedded blueprint remains possible), and retains an easy path to full standalone deployment for multi-language consumption without forcing it everywhere immediately.

---

## 2. Target end-state (what "done" means)

### 2.1 Repositories and their responsibilities

#### 2.1.1 aws-file-transfer-api (NEW canonical backend repo)

Path: `~/repos/work/infra-stack/aws-file-transfer-api`

Delivers:

- Core backend library: env config, policy, scoping rules, S3 presign service layer, error envelope, request/response models
- Framework adapters:
  - Flask blueprint factory (for Dash/Flask embedding)
  - FastAPI router + create_app() (for standalone API deployments)
- Quality gates: ruff + mypy + pytest + CI
- Docs: stable API contract, configuration reference, security guidance, examples
- Optional auth helpers (pluggable): session-based and/or JWT verifier modules

#### 2.1.2 aws-dash-s3-file-handler (EXISTING, becomes UI + integration wrapper)

Path: `~/repos/work/infra-stack/aws-dash-s3-file-handler`

Keeps:

- Dash components (S3FileUploader, asset tags helper)
- Packaged JS/CSS assets for multipart upload UI
- Convenience re-exports of backend types/functions from aws-file-transfer-api to avoid breaking consumers

Removes:

- All backend service logic, models, env parsing, framework adapters (moved to aws-file-transfer-api)

#### 2.1.3 pca-analysis-dash (EXISTING app repo)

Path: `~/repos/work/pca-analysis-dash/dash-pca`

Changes:

- Deletes/retire any duplicated file-transfer endpoints and S3 presign logic in-app
- Uses aws-file-transfer-api (directly or via re-exports) + aws-dash-s3-file-handler UI integration
- Enforces 200MB cap via UploadPolicy (app-specific)

#### 2.1.4 container-craft (EXISTING)

Path: `~/repos/work/infra-stack/container-craft`

No contract changes. Verify that:

- Transfer Acceleration enabled in dev+prod for file-transfer bucket
- CORS AllowedOrigins uses only ServiceDNS (recommended pattern)
- FILE_TRANSFER_USE_ACCELERATE_ENDPOINT is injected and honored by backend presign logic

---

## 3. Public API contract (must remain stable)

### 3.1 HTTP endpoints (control plane)

Default prefix remains /api/file-transfer for embedded apps, with an additional versioned prefix supported by the standalone service (/v1/file-transfer).

Paths

- POST /uploads/initiate
- POST /uploads/sign-parts
- POST /uploads/complete
- POST /uploads/abort
- POST /downloads/presign

### 3.2 Key scoping rules (non-negotiable)

- Keys are server-generated:
  - {UPLOAD_PREFIX}/{scope_id}/{uuid}/{sanitized_filename}
- scope_id must be derived from an app-defined source:
  - default: validated session UUID from client
  - recommended: derived from authenticated principal (user_id / tenant_id), ignoring client-provided session_id

### 3.3 Error envelope (non-negotiable)

All non-2xx responses:

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "Human readable message",
    "request_id": "optional"
  }
}
```

### 3.4 Transfer Acceleration behavior

If FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true:

- Bucket must have Transfer Acceleration enabled
- Presigned URLs must be generated against accelerate endpoint (server-side client config)
- Browser uses returned presigned URL as-is

Relevant AWS + boto3 docs:

- boto3 configuration (use_accelerate_endpoint): <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html>
- botocore config reference: <https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html>
- Transfer Acceleration examples: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration-examples.html>

---

## 4. Repo structure and tooling (2026 best-practice baseline)

### 4.1 Python + dependency policy

- Python: target 3.12+ (support 3.13 in CI)
- Use uv for locking + reproducibility: <https://docs.astral.sh/uv/>
- Use ruff (format + lint): <https://docs.astral.sh/ruff/>
- Use mypy (strict): <https://mypy.readthedocs.io/>
- Use pytest: <https://docs.pytest.org/>
- Use Pydantic v2 for request/response models: <https://docs.pydantic.dev/latest/>
- Use boto3/botocore for presigning and multipart operations:
  - boto3 presigned URLs guide: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html>
  - AWS presigned URL concepts: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>

### 4.2 aws-file-transfer-api - proposed directory tree

```
aws-file-transfer-api/
  README.md
  AGENTS.md
  pyproject.toml
  uv.lock
  src/
    aws_file_transfer_api/
      __init__.py
      version.py
      config.py
      policy.py
      errors.py
      models.py
      scoping.py
      s3_client.py
      service.py
      adapters/
        __init__.py
        flask_blueprint.py
        fastapi_router.py
        fastapi_app.py
      auth/
        __init__.py
        interfaces.py
        jwt_auth0.py
      observability/
        __init__.py
        logging.py
        request_id.py
  tests/
    test_service_unit.py
    test_scoping.py
    test_flask_adapter.py
    test_fastapi_adapter.py
  docs/
    architecture/
      adr/
      spec/
    reference/
      configuration.md
      api-contract.md
      security.md
    examples/
      flask_embedded.md
      fastapi_standalone.md
```

### 4.3 aws-dash-s3-file-handler - resulting shape

Keep:

```
src/aws_dash_s3_file_handler/
  __init__.py
  dash_integration.py
  assets/
    file_transfer.js
    file_transfer.css
```

Remove (moved to backend repo):

- config.py, errors.py, models.py, scoping.py, s3_client.py, service.py
- flask_integration.py, fastapi_integration.py

---

## 5. Implementation plan - PR-sized breakdown with checklists

Legend:

- [ ] not done
- [x] done
- (TEST) requires tests
- (DOC) requires docs update

---

### PR 1 - Create aws-file-transfer-api repository skeleton (tooling + CI)

[ ] 5.1.1 Initialize repo

- [ ] Create new repo directory at `~/repos/work/infra-stack/aws-file-transfer-api`
- [ ] Add pyproject.toml with:
  - [ ] project metadata + src layout
  - [ ] dependency groups:
    - [ ] core: boto3, pydantic
    - [ ] flask: flask (optional)
    - [ ] fastapi: fastapi, uvicorn[standard] (optional)
    - [ ] dev: ruff, mypy, pytest, pytest-cov, types-* as needed
- [ ] Add uv.lock and document uv sync usage
- [ ] Add ruff config (match existing style)
- [ ] Add mypy strict config

[ ] 5.1.2 CI workflows

- [ ] Add GitHub Actions workflow:
  - [ ] uv sync --group dev
  - [ ] ruff format check + ruff lint
  - [ ] mypy
  - [ ] pytest (+ coverage)
  - [ ] build wheel/sdist (uv build)

[ ] 5.1.3 Docs bootstrap (DOC)

- [ ] README.md with:
  - [ ] what this repo is
  - [ ] embedded vs standalone usage
  - [ ] environment variables (mirror container-craft)
- [ ] AGENTS.md instructing Codex how to run tests, style, and how to update PLAN.md

Acceptance criteria

- [ ] uv run ruff check . passes
- [ ] uv run mypy . passes
- [ ] uv run pytest passes

---

### PR 2 - Migrate backend modules from aws-dash-s3-file-handler into aws-file-transfer-api (core only)

[ ] 5.2.1 Copy/move modules
From `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/` into `~/repos/work/infra-stack/aws-file-transfer-api/src/aws_file_transfer_api/`:

- [ ] config.py -> config.py (or split config/policy/scoping if cleaner)
- [ ] errors.py
- [ ] models.py
- [ ] scoping.py (if separate; otherwise extract now)
- [ ] s3_client.py
- [ ] service.py
- [ ] Update imports + module names to aws_file_transfer_api.*
- [ ] Ensure no Dash or dash-mantine imports exist in backend repo

[ ] 5.2.2 Normalize naming (minimal, non-breaking)

- [ ] Keep public class/function names stable:
  - FileTransferEnvConfig
  - UploadPolicy
  - AuthPolicy
  - FileTransferService
  - request/response models
- [ ] Ensure FileTransferEnvConfig.from_env(...) remains supported

[ ] 5.2.3 Add observability hooks

- [ ] Add request-id helper and logging helpers (thin wrappers)
- [ ] Ensure presigned URLs are never logged (add explicit guard and a regression test)

[ ] 5.2.4 Port unit tests (TEST)

- [ ] Move service unit tests (FakeS3Client, FakeFactory, test_initiate_upload_* etc.)
- [ ] Ensure they pass unchanged except for import paths

Acceptance criteria

- [ ] Unit tests validate:
  - single vs multipart strategy selection
  - parts signing returns stable mapping
  - complete sorts parts by part number
  - scope checks prevent prefix escapes

---

### PR 3 - Add framework adapters in aws-file-transfer-api (Flask + FastAPI)

[ ] 5.3.1 Flask blueprint adapter

- [ ] Implement adapters/flask_blueprint.py:
  - register_file_transfer_blueprint(flask_app, *, env_config, upload_policy, auth_policy, ...)
- [ ] Keep response shapes identical to existing contract and existing JS expectations
- [ ] Ensure stable error envelope everywhere

[ ] 5.3.2 Flask adapter tests (TEST)

- [ ] Create tests that call endpoints with Flask test client:
  - initiate success
  - initiate forbidden on size/type
  - sign-parts forbidden if key out of scope
  - complete/abort success paths

[ ] 5.3.3 FastAPI router + app

- [ ] Implement adapters/fastapi_router.py:
  - create_router(service, prefix="/api/file-transfer")
- [ ] Implement adapters/fastapi_app.py:
  - create_app(..., prefix="/api/file-transfer") returns FastAPI app
- [ ] Provide an executable entrypoint for local run (uvicorn)
- [ ] Add optional CORS middleware configuration (FastAPI mode only)

[ ] 5.3.4 FastAPI adapter tests (TEST)

- [ ] Use fastapi.testclient.TestClient to validate endpoints and response shapes

Acceptance criteria (DOC + TEST)

- [ ] Both adapters produce identical JSON shapes for the same inputs
- [ ] API contract remains compatible with current `assets/file_transfer.js`

FastAPI references:

- FastAPI docs: <https://fastapi.tiangolo.com/>
- FastAPI release notes: <https://fastapi.tiangolo.com/release-notes/>
- FastAPI GitHub releases: <https://github.com/fastapi/fastapi/releases>

---

### PR 4 - Auth interfaces + optional Auth0 JWT verifier module (pluggable)

Constraint: auth must remain optional and pluggable. Do not hardwire Auth0 into the core service layer.

[ ] 5.4.1 Define auth interface

- [ ] auth/interfaces.py:
  - Principal shape (user_id, tenant_id, scopes)
  - AuthContext with raw request headers + session_id + optional token
  - Verifier callable protocol returning Principal or raising
- [ ] Update AuthPolicy to support:
  - validating session_id format (dev/local)
  - overriding scope_id derivation (principal-based)

[ ] 5.4.2 Implement Auth0 JWT verifier (optional)

- [ ] auth/jwt_auth0.py:
  - JWKS fetch + caching
  - verify iss, aud, exp, signature
  - emit Principal
- [ ] Document required env vars for standalone service use:
  - AUTH0_DOMAIN, AUTH0_AUDIENCE, AUTH0_ISSUER

[ ] 5.4.3 Docs (DOC)

- [ ] docs/reference/security.md:
  - embedded mode vs standalone mode auth patterns
  - recommended: derive scope_id from principal, not client session_id

Acceptance criteria (TEST)

- [ ] Core service layer still works without auth module installed
- [ ] JWT module has unit tests (mock JWKS)

---

### PR 5 - Refactor aws-dash-s3-file-handler to depend on aws-file-transfer-api and remove duplication

Repo path: `~/repos/work/infra-stack/aws-dash-s3-file-handler`

[ ] 5.5.1 Add dependency

- [ ] Update pyproject.toml:
  - depend on aws-file-transfer-api (path dependency during dev; pinned version for releases)

[ ] 5.5.2 Delete backend modules (or replace with thin import-only shims)

- [ ] Remove these files from dash handler repo (no duplicate logic):
  - config.py, errors.py, models.py, s3_client.py, service.py
  - flask_integration.py, fastapi_integration.py
- [ ] Update imports in remaining Dash code

[ ] 5.5.3 Preserve backward compatibility

- [ ] In aws_dash_s3_file_handler/__init__.py, re-export:
  - FileTransferEnvConfig, UploadPolicy, AuthPolicy
  - FileTransferService
  - register_file_transfer_blueprint / create_fastapi_app helpers (imported from backend repo)
- [ ] Avoid noisy warnings; keep compatibility first

[ ] 5.5.4 Ensure JS assets remain compatible

- [ ] assets/file_transfer.js continues to:
  - call /uploads/initiate, /uploads/sign-parts, /uploads/complete, /uploads/abort
  - send credentials: "same-origin" (OK for embedded blueprint mode)
- [ ] Keep file-transfer-session-id node behavior unchanged (until later refactor)

[ ] 5.5.5 Update tests (TEST)

- [ ] Remove backend tests from dash handler repo (they live in backend repo now)
- [ ] Keep minimal tests for:
  - Dash component layout creation
  - Asset tag generation includes JS/CSS
  - Smoke test import works

Acceptance criteria

- [ ] aws-dash-s3-file-handler contains no backend logic, only UI + re-exports
- [ ] Existing consumer code can keep importing from aws_dash_s3_file_handler without changes

---

### PR 6 - Refactor pca-analysis-dash to use the final packages (no duplicated file-transfer backend)

Repo path: `~/repos/work/pca-analysis-dash/dash-pca`

[ ] 5.6.1 Dependencies

- [ ] Add dependencies:
  - aws-dash-s3-file-handler
  - aws-file-transfer-api
- [ ] Ensure uv.lock updates cleanly

[ ] 5.6.2 Remove duplicated backend endpoints

- [ ] Delete/retire PCA repo’s own file-transfer blueprint module(s):
  - src/api/file_transfer.py
  - src/services/file_transfer_service.py
  - any duplicated JS uploader assets
- [ ] Replace registration with:
  - aws_file_transfer_api.adapters.flask_blueprint.register_file_transfer_blueprint(...)
  - or the re-exported function from aws_dash_s3_file_handler

[ ] 5.6.3 Enforce PCA app policy (200MB + CSV/XLSX)

- [ ] Instantiate UploadPolicy with:
  - max_upload_bytes = 200 *1024* 1024
  - allowed_extensions = {".csv", ".xlsx"}
  - multipart threshold + part size from env (or override if needed)
- [ ] Ensure UI rejects oversize at initiate (presign time)

[ ] 5.6.4 UI integration

- [ ] Ensure PCA uses S3FileUploader(...) and FileTransferAssets()
- [ ] Ensure callback pipeline consumes (bucket, key, size_bytes, content_type) result from uploader stores
- [ ] Keep local-dev fallback when FILE_TRANSFER_ENABLED=false (existing behavior)

[ ] 5.6.5 Tests (TEST)

- [ ] Add/adjust tests to confirm:
  - file-transfer enabled path uses S3 object reference, not base64
  - disabled path still works (smoke)
- [ ] Run uv run pytest -m "not e2e"

[ ] 5.6.6 Docs (DOC)

- [ ] Update PCA README/docs to:
  - explain how to enable file transfer via container-craft config
  - explicitly state 200MB cap for this app
  - document required environment variables and their source (container-craft)

---

### PR 7 - Integration verification: container-craft wiring + transfer acceleration + CORS

Repo path: `~/repos/work/infra-stack/container-craft`

[ ] 5.7.1 Verify service configs

- [ ] In PCA configs:
  - `~/repos/work/pca-analysis-dash/dash-pca/configs/service/dev.yml`
  - `~/repos/work/pca-analysis-dash/dash-pca/configs/service/prod.yml`
  ensure:
  - file_transfer_enabled: "true"
  - file_transfer_enable_transfer_acceleration: "true"
  - file_transfer_cors_allowed_origins: ServiceDNS-only origin(s) in prod
- [ ] Ensure workflows pin container-craft @v3
- [ ] Ensure ECS env var FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true is injected when acceleration enabled

[ ] 5.7.2 Runtime validation checklist (manual)

- [ ] Upload small CSV (single PUT path)
- [ ] Upload near-cap file (~200MB) (multipart if threshold < 200MB)
- [ ] Confirm browser can read ETag header (S3 CORS ExposeHeaders includes ETag)
- [ ] Confirm presigned URL host uses accelerate endpoint when enabled
- [ ] Confirm download presign works and does not proxy bytes through Dash

Acceptance criteria

- [ ] No upload/download bytes traverse ECS (except app-generated exports uploaded by app logic, if still present)
- [ ] Acceleration + CORS behave correctly in both dev and prod

AWS docs to use for troubleshooting:

- S3 CORS: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html>
- Manage CORS examples: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/ManageCorsUsing.html>
- Presigned URLs overview: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>

---

### PR 8 - Releases, versioning, and final cleanup

[ ] 5.8.1 Version policy

- [ ] aws-file-transfer-api: start at 0.1.0 (or next available)
- [ ] aws-dash-s3-file-handler: bump minor (behavioral refactor but compatible API via re-exports)

[ ] 5.8.2 Changelogs (DOC)

- [ ] Add CHANGELOG.md entries in both repos

[ ] 5.8.3 Final PLAN.md hygiene (DOC)

- [ ] Mark all completed tasks [x]
- [ ] Add final "Operational Notes" section with common failure modes (CORS, missing env vars, accel disabled)

---

## 6. Progress Log (Codex must update during implementation)

- YYYY-MM-DD: PR# - summary, notable decisions, follow-ups
- YYYY-MM-DD: PR# - summary, notable decisions, follow-ups

---

## 7. Non-goals (explicitly out of scope for this plan)

- Building an async compute pipeline (Batch/ECS workers) for PCA or other analyses
- Implementing dataset-specific parsing/validation beyond extension/size policy
- Replacing container-craft’s file-transfer CloudFormation stacks (contract is assumed correct)

---

## 8. Final "Definition of Done" checklist

[ ] aws-file-transfer-api repo exists, CI green, tests cover core service and adapters  
[ ] aws-dash-s3-file-handler has no backend code (only UI + re-exports)  
[ ] pca-analysis-dash has no duplicated file-transfer endpoints, uses packages cleanly  
[ ] Transfer Acceleration works (dev + prod), URLs presign against accelerate endpoint when enabled  
[ ] CORS origins correct and minimal; ETag exposed; no wildcard + credentials mismatch  
[ ] All repos pass ruff, mypy, pytest under uv run  
[ ] PLAN.md updated with completed checkboxes and notes

---

## References and changelogs (full URLs)

FastAPI and ecosystem

- FastAPI docs: <https://fastapi.tiangolo.com/>
- FastAPI release notes: <https://fastapi.tiangolo.com/release-notes/>
- FastAPI "About versions": <https://fastapi.tiangolo.com/deployment/versions/>
- FastAPI GitHub: <https://github.com/fastapi/fastapi>
- FastAPI releases: <https://github.com/fastapi/fastapi/releases>
- Pydantic docs: <https://docs.pydantic.dev/latest/>
- pydantic-settings docs: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
- Uvicorn docs: <https://www.uvicorn.org/>
- uv docs: <https://docs.astral.sh/uv/>
- ruff docs: <https://docs.astral.sh/ruff/>
- mypy docs: <https://mypy.readthedocs.io/>
- pytest docs: <https://docs.pytest.org/>

AWS and boto3

- boto3 S3 presigned URLs guide: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html>
- boto3 configuration (use_accelerate_endpoint): <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html>
- botocore config reference: <https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html>
- S3 presigned URL overview: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>
- S3 presigned URL upload: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html>
- S3 multipart upload overview: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html>
- S3 multipart upload limits: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html>
- S3 CORS: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html>
- S3 CORS elements: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/ManageCorsUsing.html>
- Transfer Acceleration: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html>
- Transfer Acceleration examples: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration-examples.html>

Internal references (local paths, accessible outside this chat)

- container-craft:
  - `~/repos/work/infra-stack/container-craft/infra/file_transfer/s3.yml`
  - `~/repos/work/infra-stack/container-craft/infra/ecs/service.yml`
  - `~/repos/work/infra-stack/container-craft/src/container-craft/settings/service.yml`
  - `~/repos/work/infra-stack/container-craft/templates/3m.yml`
- aws-dash-s3-file-handler:
  - `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/service.py`
  - `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/flask_integration.py`
  - `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/fastapi_integration.py`
  - `~/repos/work/infra-stack/aws-dash-s3-file-handler/src/aws_dash_s3_file_handler/assets/file_transfer.js`
- pca-analysis-dash:
  - `~/repos/work/pca-analysis-dash/dash-pca/src/api/file_transfer.py`
  - `~/repos/work/pca-analysis-dash/dash-pca/src/services/file_transfer_service.py`
  - `~/repos/work/pca-analysis-dash/dash-pca/configs/service/dev.yml`
  - `~/repos/work/pca-analysis-dash/dash-pca/configs/service/prod.yml`
