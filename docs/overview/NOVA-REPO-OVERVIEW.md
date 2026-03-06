# Nova Runtime Repository Overview

## 1) What Nova is

Nova is the canonical runtime monorepo for file-transfer orchestration and token verification services. It provides a control plane for transfer and async job workflows, plus an auth API for token verify/introspect operations. Nova is not a byte-streaming proxy for file payloads; file movement is delegated through planned resources and storage integrations.

## 2) Monorepo map

- `apps/nova_file_api_service`: ASGI service wrapper that boots the file API runtime package.
- `apps/nova_auth_api_service`: ASGI service wrapper that boots the auth API runtime package.
- `packages/nova_file_api`: Main transfer + jobs control-plane implementation.
- `packages/nova_auth_api`: Token verify/introspect API implementation.
- `packages/nova_dash_bridge`: Integration bridge adapters for Dash/Flask/FastAPI clients.
- `packages/contracts`: Contract artifacts, fixtures, and conformance helpers.
- `packages/nova_sdk_py_file`: Committed generated Python SDK for the file API.
- `packages/nova_sdk_py_auth`: Committed generated Python SDK for the auth API.
- `packages/nova_sdk_file_core`: Internal generated TypeScript operation catalog for the file API.
- `packages/nova_sdk_auth_core`: Internal generated TypeScript operation catalog for the auth API.
- `packages/nova_sdk_fetch`: Shared internal TypeScript transport/runtime helpers for generated catalogs.
- `packages/nova_sdk_r_file`: Internal generated R operation catalog for the file API.
- `packages/nova_sdk_r_auth`: Internal generated R operation catalog for the auth API.
- `infra/nova` and `infra/runtime`: CloudFormation stacks for CI/CD foundation and runtime environments.

SDK release posture for this wave:

- Python packages are the only release-grade public SDK surface.
- TypeScript and R packages remain internal/generated catalogs until a later
  promotion wave.

OpenAPI and SDK generation authority for this topology:

- Canonical service contracts are committed under `packages/contracts/openapi/`.
- `scripts/contracts/export_openapi.py` refreshes and checks the committed OpenAPI artifacts.
- `scripts/release/generate_clients.py` refreshes and checks the internal TypeScript and R catalogs.
- `scripts/release/generate_python_clients.py` refreshes and checks the committed Python SDK trees.

```mermaid
flowchart TB
    subgraph Apps
        A1["apps/nova_file_api_service"]
        A2["apps/nova_auth_api_service"]
    end
    subgraph RuntimePackages
        P1["packages/nova_file_api"]
        P2["packages/nova_auth_api"]
        P3["packages/nova_dash_bridge"]
        P4["packages/contracts"]
    end
    subgraph Infra
        I1["infra/nova"]
        I2["infra/runtime"]
    end

    A1 --> P1
    A2 --> P2
    P3 --> P1
    P4 --> P1
    P4 --> P2
    I1 --> A1
    I1 --> A2
    I2 --> A1
    I2 --> A2
```

## 3) Runtime architecture at a glance

- `nova_file_api` serves canonical `/v1/*` transfer and job endpoints.
- Requests pass through auth, validation, idempotency, and service-layer orchestration.
- Async workloads are published to queue backends and completed by workers.
- Workers report completion to the internal callback endpoint (`/v1/internal/jobs/{job_id}/result`).
- Worker runtime is launched via packaged command `nova-file-worker` and
  canonical `JOBS_*` env contract (`JOBS_RUNTIME_MODE=worker`,
  `JOBS_API_BASE_URL`, `JOBS_SQS_QUEUE_URL`, `JOBS_WORKER_UPDATE_TOKEN`).
- Health and observability surfaces are exposed via:
  - `/v1/health/live`
  - `/v1/health/ready`
  - `/metrics/summary`
- `nova_auth_api` separately serves token verification/introspection capabilities.

```mermaid
flowchart LR
    C["Client"] --> API["nova_file_api /v1 endpoints"]
    API --> AUTH["Auth and validation boundary"]
    AUTH --> ORCH["Transfer and jobs orchestration"]
    ORCH --> SQS["Queue backend"]
    SQS --> W["Worker"]
    W --> CB["POST /v1/internal/jobs/{job_id}/result"]
    CB --> API
    API --> OBS["/v1/health/live /v1/health/ready /metrics/summary"]
```

## 4) Package responsibilities and interactions

- `nova_file_api` owns:
  - Transfer orchestration endpoints and request/response models.
  - Async job submission and status/result lifecycle.
  - Idempotency cache semantics and activity recording integrations.
  - Runtime capability/resource planning endpoints.
- `nova_auth_api` owns:
  - Auth token verification and introspection routes.
  - Standardized auth error envelope behavior.
- `nova_dash_bridge` owns:
  - Framework adapters that let Dash/Flask/FastAPI apps consume Nova-style transfer flows without redefining server contracts.
- `contracts` owns:
  - Test fixtures, schemas, and conformance artifacts used by release and integration checks.
- generated SDK packages own:
  - committed Python SDK distributions for the public file/auth client surface.
  - internal TypeScript and R catalogs derived from the canonical OpenAPI artifacts.

```mermaid
flowchart LR
    FILE["nova_file_api"] --> CACHE["idempotency and cache logic"]
    FILE --> ACT["activity and job lifecycle"]
    FILE --> ROUTES["canonical v1 routes"]
    AUTH["nova_auth_api"] --> TOK["verify and introspect"]
    BRIDGE["nova_dash_bridge"] --> FILE
    CONTRACTS["contracts"] --> FILE
    CONTRACTS --> AUTH
```

## 5) Canonical API surface and route guardrails

### Allowed runtime route families

- `/v1/transfers/*`
- `/v1/jobs*`
- `/v1/internal/jobs/{job_id}/result` (internal worker callback only)
- `/v1/capabilities`
- `/v1/resources/plan`
- `/v1/releases/info`
- `/v1/health/live`
- `/v1/health/ready`
- `/metrics/summary`

### Disallowed runtime route families

- `/api/*`
- `/api/v1/*`
- `/healthz`
- `/readyz`

No compatibility aliases or namespace shims should be added for disallowed families.

### High-level endpoint intent map

| Path family | Primary consumer | Intent |
|---|---|---|
| `/v1/transfers/*` | External clients and app integrations | Plan and orchestrate file-transfer operations |
| `/v1/jobs*` | External clients and integrations | Submit and track async jobs |
| `/v1/internal/jobs/{job_id}/result` | Internal worker | Record job completion result |
| `/v1/capabilities` | Clients / UI / automation | Discover enabled runtime capabilities |
| `/v1/resources/plan` | Clients / operators | Get resource planning metadata |
| `/v1/releases/info` | Operators / tooling | Surface runtime release info |
| Health + metrics endpoints | Platform and operations tooling | Liveness, readiness, and summary metrics |

```mermaid
flowchart TB
    subgraph PublicV1
        T["/v1/transfers/*"]
        J["/v1/jobs*"]
        C["/v1/capabilities"]
        R["/v1/resources/plan"]
        RI["/v1/releases/info"]
        HL["/v1/health/live"]
        HR["/v1/health/ready"]
    end
    INT["/v1/internal/jobs/{job_id}/result internal only"]
    M["/metrics/summary"]
    BAD["Disallowed: /api/* /api/v1/* /healthz /readyz"]

    T --> J
    J --> INT
    HL --> HR
    HR --> M
    BAD -. not allowed .- PublicV1
```

## 6) Client usage flows

### Transfer flow (typical)

1. Call `/v1/capabilities` to discover supported operations and policy posture.
2. Call transfer planning/creation endpoints under `/v1/transfers/*`.
3. Follow returned transfer plan details to complete storage-side actions.
4. Poll status endpoints as needed for lifecycle updates.

### Async job flow (typical)

1. Submit work via `POST /v1/jobs`.
2. Receive job metadata and track using `/v1/jobs*` read endpoints.
3. Internal worker processes queue message and posts completion to `/v1/internal/jobs/{job_id}/result`.
4. Client reads terminal state and result through public job endpoints.

### Auth usage

1. Client or service calls auth API verify/introspect endpoints for token checks.
2. Runtime services enforce auth decisions at request boundaries.

## 7) AWS and deployment topology

### Runtime plane (high level)

- Compute: ECS/Fargate services (API + worker roles).
- Edge and ingress: ALB and WAF integration.
- Storage/data: S3 (transfer resources), DynamoDB (activity/state patterns), Redis/cache backends.
- Async: SQS queues with DLQ handling.
- Security: IAM + KMS-backed encryption posture.
- Observability: CloudWatch logs/metrics and summary surfaces.

### Delivery plane (high level)

- GitHub Actions workflows orchestrate quality gates, release, and environment promotions.
- AWS CodePipeline/CodeBuild/CodeConnections and artifact controls are represented in the infra stacks and release workflows.
- Promotion model is artifact-forward (build once, promote across lanes).
- Runtime service deployment is ECS-native blue/green on `AWS::ECS::Service`
  with ALB target groups, CloudWatch deployment alarms, lifecycle hooks, and
  WAF on the public ALB path.
- Runtime stack deploy stages are change-set first (create/update then execute)
  with rollback-on-failure behavior delegated to CloudFormation/ECS deploy controls.
- Release/deploy workflows declare explicit concurrency groups to serialize
  lane-specific operations.

```mermaid
flowchart LR
    GH["GitHub Actions"] --> BUILD["Build and quality gates"]
    BUILD --> ART["Artifact and package outputs"]
    ART --> CD["CodePipeline and CodeBuild promotion"]
    CD --> ECS["ECS Fargate API and worker services"]
    ECS --> SQS["SQS and DLQ"]
    ECS --> S3["S3 transfer resources"]
    ECS --> DDB["DynamoDB activity and state"]
    ECS --> REDIS["Redis cache"]
    ECS --> CW["CloudWatch logs and metrics"]
    ECS --> KMS["KMS protected data paths"]
    ALB["ALB, WAF, and ECS blue/green listeners"] --> ECS
```

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub Actions
    participant AWS as AWS Delivery Plane
    participant RT as Runtime Lane

    Dev->>GH: Push tag or release change
    GH->>GH: Run lint type test contract gates
    GH->>AWS: Publish artifact and trigger promotion
    AWS->>RT: Deploy immutable artifact to target lane
    RT-->>GH: Report deployment and validation status
```

## 8) Security and reliability invariants

- Queue publish failures for `POST /v1/jobs` must return `503` with `error.code = "queue_unavailable"`.
- Failed enqueue responses must not be replay-cached by idempotency mechanisms.
- `/v1/health/ready` evaluates only traffic-critical dependencies.
- Missing or blank `FILE_TRANSFER_BUCKET` must fail readiness.
- Worker callback with `status=succeeded` must clear `error` to `null`.
- Presigned URLs, JWTs, and signed query values must not be logged.
- Synchronous JWT verification must not run directly on async event-loop paths; threadpool boundaries are required.
- Config coupling constraints are enforced for backend selections (for example queue/activity backends requiring corresponding resource settings).

## 9) How to explain Nova in 10 minutes (talk track)

### Minute-by-minute script

1. Minute 1: Purpose and scope
- “Nova is our transfer/job control plane and auth verification runtime in one monorepo.”
- “It standardizes canonical `/v1/*` API behavior and operational guardrails.”

2. Minute 2: Monorepo layout
- Walk apps vs packages.
- Emphasize that `apps/*` are wrappers and `packages/*` hold core logic.

3. Minutes 3-4: Architecture flow
- Explain request path into `nova_file_api`.
- Explain queue-based async job lifecycle and internal worker callback.

4. Minute 5: API surface rules
- Show allowed route families and strict no-legacy aliases rule.

5. Minutes 6-7: Client integration story
- Capabilities -> transfer plan -> transfer execution.
- Job submit -> worker completion -> status/result reads.

6. Minutes 8-9: AWS topology and delivery
- Map services to ECS, SQS, S3, DynamoDB, Redis, ALB/WAF, CloudWatch, KMS.
- Explain release/promotion posture at high level.

7. Minute 10: Reliability and security guarantees
- Cover queue-unavailable semantics, readiness strictness, sensitive logging guardrails, and auth threadpool boundary.

### Quick FAQ responses

- “Why no `/api/v1/*` alias?”
  - Hard-cut canonical route policy to avoid dual contract drift.
- “Where is business logic?”
  - In `packages/nova_file_api` and `packages/nova_auth_api`; apps are thin runtime wrappers.
- “How do Dash clients integrate?”
  - Through `packages/nova_dash_bridge` adapters, without forking core runtime contracts.
- “What is the async completion boundary?”
  - Worker posts to `/v1/internal/jobs/{job_id}/result`; clients read via `/v1/jobs*`.

## 10) Glossary and source-of-truth references

### Glossary

- Control plane: API-level orchestration and state transitions, not payload proxying.
- Canonical surface: Approved route namespace and behavior contract.
- Lane: Environment stage in delivery/promotion flow (for example dev/nonprod/prod).
- Worker callback: Internal endpoint used to publish terminal job outcomes.

### Active authority references

- `AGENTS.md`
- `README.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md`

### Historical context (non-authoritative for current behavior)

- `PRD.md`
- `FINAL-PLAN.md`
- `docs/plan/HISTORY-INDEX.md`
- `docs/history/**`
