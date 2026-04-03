# Executive Diagnosis

## 15-minute scoping plan

| Window | Goal | Result |
| --- | --- | --- |
| 0–5 min | Verify Nova repo truth, public contract, active runtime, and hard bans | Confirmed Nova is already a control plane for direct-to-S3 uploads/downloads, with `/v1/transfers/*`, `/v1/exports*`, Step Functions exports, DynamoDB correctness state, browser-only Dash helper, and CDK-managed Lambda/API/WAF deployment. |
| 5–10 min | Validate AWS hard limits and service behaviors that matter for 500 GB / 1 TB+ workloads | Confirmed the key boundaries: API Gateway is still a 10 MB control plane, not a bulk upload path; S3 multipart supports up to 48.8 TiB objects with 10,000 parts; Step Functions state payload/history limits remain real design constraints. ([AWS Documentation][1]) |
| 10–15 min | Score candidate architectures and reject weak ones | The correct answer is not “replace Nova.” The correct answer is “keep Nova’s data plane shape, modernize the control plane, and add a second export lane only where giant copies justify it.” |

## 1. Executive Summary

* Nova already uses the correct first-principles upload architecture: API as control plane, S3 as data plane. That is why 500 GB single-file uploads are feasible here, while proxying bytes through API Gateway/Lambda would be architecturally wrong. API Gateway still caps payloads at 10 MB, while S3 multipart supports up to 48.8 TiB with 10,000 parts of 5 MiB–5 GiB. ([AWS Documentation][1])
* The repo’s current baseline is stronger than expected: direct presigned single/multipart uploads, resumable browser upload with `/uploads/introspect`, explicit `/v1/exports`, Step Functions Standard orchestration, DynamoDB idempotency/state, WAF, reserved concurrency, and S3 lifecycle cleanup are all already in place.
* The biggest current scale gap is not S3 capacity. It is Nova’s control plane: env-static limits, no durable upload-session state, no app/workload-level quota ledger, and browser defaults that are tuned for modest flows rather than 500 GB uploads.
* The most immediate performance defect is the browser helper’s tiny signing window. Today the browser uploader defaults to `maxConcurrency=4` and `signBatchSize=8`. With the current 128 MiB part size, a 500 GiB file yields about 4,000 parts and about 500 `sign-parts` control-plane calls. That is unnecessary API churn.
* The largest export risk is the current inline multipart copy path. One 5-minute, 1,024 MiB Lambda task currently reuses the upload part size for server-side S3 copies. That is fine for moderate exports, but it is the wrong tuning basis for giant export copies because server-side copy can safely use much larger parts.
* Step Functions Standard should stay. But giant export fan-out must not push per-part manifests into execution state because Standard workflows still have 256 KiB input/output limits and 25,000 event-history limits. Store manifests/part state outside the execution payload and pass references only. ([AWS Documentation][2])
* The selected target is additive and contract-safe: keep direct S3 multipart, keep Step Functions Standard, keep DynamoDB as canonical correctness state, add `UploadSession` + `TransferUsageWindow` tables, AppConfig-backed effective policies, adaptive part sizing/batching, a janitor/reconciler, cooperative export cancel, and an internal queue-backed large-export copy lane used only above a measured threshold. SQS long polling and DLQs fit that worker lane well. ([AWS Documentation][3])
* Transfer Acceleration should be opt-in, not global default. AWS positions it for centralized buckets with geographically distributed users and notes additional transfer charges. That fits an enterprise “giant remote upload” tier, not all workloads. ([AWS Documentation][4])
* S3 Express One Zone should not become Nova’s default authoritative upload store. It is single-AZ, uses directory buckets and `CreateSession`-based auth, and changes the storage/auth model without solving Nova’s main current bottlenecks. ([Amazon Web Services, Inc.][5])
* The repo’s uploaded AWS guidance already pushes the same direction: managed services, explicit decision matrices, least-privilege IAM, bounded concurrency, and structured observability. The roadmap below stays inside those boundaries.

### Executive conclusion

Do **not** replace Nova’s upload architecture.
Do **modernize** Nova’s transfer/export control plane.

---

# Full table of findings

| Area | Current repo truth | What is good | What is weak | Action |
| --- | --- | --- | --- | --- |
| Upload data plane | `packages/nova_file_api/transfer.py` signs direct S3 single/multipart uploads | Bytes already bypass API runtime; correct shape for 500 GB objects | Control-plane defaults are not tuned for giant uploads | Keep architecture; tune policy, batching, and session state |
| Multipart resume | Browser helper uses `/uploads/introspect` and localStorage resume | Resume exists already; `ListParts` pagination supports large uploads | Resume durability is client-local only; no authoritative upload session | Add `UploadSession` state in DynamoDB |
| Upload sizing | Static defaults: threshold 100 MiB, part size 128 MiB, concurrency 4 | Safe baseline | Too many parts and too many sign calls for giant files | Make part size and sign batch dynamic by policy |
| Upload limits | `FILE_TRANSFER_MAX_UPLOAD_BYTES` default 500 GiB | Requirement is already encoded | Per-app/per-workload overrides missing | Add effective policy resolution model |
| Export workflow | Step Functions Standard + DynamoDB export state | Correct explicit workflow model | Giant copy path is one inline Lambda task | Add two-lane export copy strategy |
| Export cancellation | Route marks DynamoDB record cancelled | Public contract exists | Execution is not cooperatively stopped | Persist execution ARN and call `StopExecution` |
| Observability | General health/readiness, API metrics, Step Functions alarms, WAF | Good starting posture | Missing MPU, stale session, TA spend, queue DLQ, and zombie-export signals | Add EMF custom metrics, Storage Lens, and cost alarms |
| Cost guardrails | WAF, reserved concurrency, S3 lifecycle cleanup | Basic blast-radius controls exist | No app-level byte budgets, active-session caps, or throughput cost bounds | Add quota ledger + DDB max throughput + budgets |
| Encryption | S3 bucket uses SSE-S3 | Cost-efficient default | SSE-KMS path not explicitly designed | Keep SSE-S3 unless compliance requires CMK; then use Bucket Keys |
| SDK/docs/contracts | OpenAPI + generated SDKs are authoritative | Clear regeneration path | Any additive route/field changes require disciplined regen/docs/test updates | Update OpenAPI, generated SDKs, docs, and CI gates together |

---

# Decision matrix

**Formula:** `Weighted = 0.30A + 0.30B + 0.20C + 0.10D + 0.10E`

A = Reliability & Failure Modes
B = Performance & Scale
C = Cost Efficiency
D = Operability & Operational Burden
E = Contract / Backward Compatibility Risk

| Overall path | Summary | A | B | C | D | E | Weighted | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Path A — Baseline-preserving hardening | Keep current stack; add upload sessions, dynamic policy, adaptive batching, janitor, cooperative cancel, larger inline export copy parts | 8.9 | 9.0 | 9.5 | 9.2 | 9.9 | **9.14** | Adopt as Phase 1 / fallback lane |
| Path B — High-scale hybrid | Path A plus queue-backed large-export part-copy workers and selective TA tier | 9.4 | 9.6 | 9.1 | 8.9 | 9.4 | **9.35** | **Selected target architecture** |
| Path C — Cost-minimized conservative | Path A with stricter quotas, no TA tier, and no automatic giant-export worker lane | 8.7 | 8.5 | 9.7 | 9.4 | 9.8 | **8.97** | Reject for full objective |

Why Path B wins:

* It keeps Nova’s public contract and current service choices intact.
* It solves the giant-upload problem mostly with control-plane changes, not a re-platform.
* It introduces operational complexity only where current evidence shows a real risk: giant export copy.
* It gives the cleanest cost-safety envelope because the expensive features are conditional, policy-controlled, and observable.

Cost logic is the main reason Path C loses: it is cheap, but it leaves too much giant-export reliability risk on the table. Reliability logic is the main reason “aggressive re-platform” ideas lose: they add surface area without addressing the real bottlenecks. S3 request count, Transfer Acceleration/MRAP charges, Step Functions state-transition pricing, DynamoDB request/storage pricing, and Lambda GB-second/request pricing all reinforce the same conclusion: reduce part counts, keep bytes off the API, use TA selectively, and only fan out export work when needed. ([Amazon Web Services, Inc.][6])

---

## 2. Current-state findings

### What in Nova already handles scale well

* `packages/nova_file_api` already treats the API as a transfer control plane, not a byte proxy.
* `transfer.py` already supports:

  * single PUT below threshold,
  * multipart above threshold,
  * batched part signing,
  * `ListParts`-backed introspection,
  * complete-time ETag reconciliation,
  * abort,
  * presigned download.
* Upload keys already include a UUID segment under caller scope, which is a sound object-key pattern.
* `packages/nova_dash_bridge` already has resumable multipart browser behavior and progress handling.
* `infra/nova_cdk/runtime_stack.py` already provisions:

  * Regional REST API Gateway + Regional WAF,
  * API Lambda on Python 3.13 arm64,
  * Step Functions Standard export workflow,
  * DynamoDB exports/idempotency/activity tables,
  * S3 lifecycle abort of incomplete multipart uploads after 7 days.
* Current export state is explicit and durable. That is materially better than implicit “job queue only” designs.

### Bottlenecks and hard limits observed

| Bottleneck | Evidence in repo | Why it matters |
| --- | --- | --- |
| Static upload policy | `config.py` env-only settings | No per-app/per-workload tuning or staged rollout |
| No durable upload session store | No `UploadSession` table or repo surface | No server-side active-session visibility, quotas, or durable resume metadata |
| Tiny browser signing window | `file_transfer.js` default `signBatchSize = min(16, 2*maxConcurrency)` and `maxConcurrency=4` | Excessive API chatter for giant files |
| Static upload part size | 128 MiB default for all multipart uploads | Too many parts/requests for 500 GiB files |
| Shared upload/copy part size | export copy reuses `self.config.part_size_bytes` | Upload tuning is wrong for server-side S3 copy tuning |
| Inline export copy only | one `CopyExport` Lambda task, 5 min / 1,024 MiB | Giant exports risk timeout and coarse retries |
| Cancel is state-only | `cancel_export` updates DynamoDB record only | Workflow may continue after user-visible cancel |
| Quota model incomplete | `SPEC-0005` planned but not implemented | No hard app-level cost/surge guardrails |
| MPU cleanup is coarse | lifecycle rule only | 7-day cleanup is necessary but not sufficient for rapid cost control |
| Missing transfer cost telemetry | no Storage Lens / TA / queue custom alarms | Partial failures and silent cost leakage remain easy to miss |

### Current upload control-plane inefficiency

| File size | Part size | Parts | Current browser sign batch (8) | Proposed sign batch (64) |
| ---: | ---: | ---: | ---: | ---: |
| 500 GiB | 128 MiB | 4,000 | 500 sign calls | 63 sign calls |
| 500 GiB | 256 MiB | 2,000 | 250 sign calls | 32 sign calls |
| 500 GiB | 512 MiB | 1,000 | 125 sign calls | 16 sign calls |

This is the most important first-principles observation in the whole review: Nova does **not** need a new upload platform to support 500 GiB uploads. It needs fewer parts, larger signing windows, and authoritative session policy/state.

### Explicit risk map

| Risk | Severity | Likelihood | Why |
| --- | --- | --- | --- |
| Giant browser upload overwhelms control plane | High | High | Current batch/concurrency defaults multiply `sign-parts` calls |
| Giant export copy times out | High | Medium-high | Inline copy uses 5-minute Lambda and upload-oriented part sizing |
| Zombie multipart cost | Medium | High | No session table, no stale-session alarms, lifecycle cleanup only |
| Cancel semantics mislead callers | High | Medium | Resource says cancelled; execution may still run |
| Quota/cost overrun by tenant/app | High | Medium | No active-session or byte-window enforcement |
| DDB usage table burst spend | Medium | Medium | New counters without throughput caps can spike cost |
| Browser checksum UX regression | Medium | Medium | Mandatory checksum for giant browser parts may add CPU/memory load |
| SQS duplicate part processing | Medium | High | Standard queue is at-least-once by design |

SQS’s at-least-once delivery and S3 event notification duplicates/out-of-order delivery are not problems if handlers are idempotent. They are serious problems if Nova treats them as exactly-once correctness state. ([AWS Documentation][7])

---

## 3. Gap Analysis

| Missing capability | Why it is required | Recommended fix |
| --- | --- | --- |
| Durable upload session state | Needed for quotas, resume metadata, last-activity timestamps, janitor cleanup, and operator visibility | Add `UploadSession` DynamoDB table |
| Dynamic policy by app/workload | Current env-only model cannot tune limits safely per tenant/app/tier | Add AppConfig-backed policy profiles with env safety envelope |
| App-level quota enforcement | WAF is not a quota system | Add `TransferUsageWindow` counters with conditional writes |
| Large-file-specific upload tuning | Giant files should not use the same defaults as moderate files | Dynamic part sizing and sign-window sizing |
| Separate export copy tuning | Server-side S3 copy has different optimal part size than browser upload | Add `export_copy_part_size_bytes` and `export_copy_max_concurrency` |
| Giant export worker lane | Inline copy will eventually hit timeout/retry inefficiency | Add queue-backed fan-out lane above threshold |
| Cooperative cancel | Caller intent must actually stop work | Persist execution ARN; call `StopExecution`; part workers check cancel flag |
| Stronger integrity modes | ETag/list-parts settle state is helpful but not enough for all workloads | Phased checksum policy |
| Stale MPU / ambiguous complete reconciliation | Lifecycle rules are too coarse and TTL is eventual | Scheduled janitor/reconciler workflow |
| Cost observability | No first-class visibility into incomplete MPU bytes, TA use, queue backlog, or quota rejection | Add Storage Lens, EMF, queue alarms, budget alarms |
| Contract-safe policy surface | Integrators need to know effective limits without reverse-engineering env vars | Add capability/policy endpoint and additive response fields |
| Docs / SDK / CI updates | Nova’s contract and generated clients are authoritative | Update OpenAPI, SDK generators, active docs, runbooks, infra tests |

---

## 4. Deep Research Report

### AWS docs reviewed

| Source area | Key finding | Why it matters |
| --- | --- | --- |
| S3 multipart | 10,000 parts, 5 MiB–5 GiB per part, 48.8 TiB max object; `ListParts`/`ListMultipartUploads` return 1,000 entries max | Confirms Nova’s current data-plane choice is already sufficient for 500 GiB objects; dynamic part sizing is the main lever. ([AWS Documentation][8]) |
| S3 integrity / presigned URLs | SigV4 presigned uploads support additional checksum algorithms; temporary credentials cap effective URL lifetime | Supports phased checksum hardening and confirms why short, progressive signing windows are preferable. ([AWS Documentation][9]) |
| S3 performance | At least 3,500 PUT/COPY/POST/DELETE or 5,500 GET/HEAD requests per second per partitioned prefix; no limit to prefix count | Confirms S3 itself is not Nova’s bottleneck for 1 TiB+ aggregate upload bursts. ([AWS Documentation][10]) |
| Transfer Acceleration | Best for globally distributed users uploading to a centralized bucket; extra charges apply | Supports opt-in rather than default enablement. ([AWS Documentation][4]) |
| S3 Express One Zone | Single-AZ durability/availability model; directory buckets; `CreateSession`-based auth | Good specialized storage tier, poor default fit for Nova’s current contract. ([Amazon Web Services, Inc.][5]) |
| API Gateway | REST/HTTP APIs still enforce 10 MB payload limits; account throttles exist; timeout changes beyond 29s are possible but not relevant to bulk uploads | Confirms API must remain control plane only. ([AWS Documentation][1]) |
| Lambda | 15-minute max duration; memory/CPU coupling; AWS recommends Power Tuning | Justifies memory tuning and benchmark gating for copy handlers. ([AWS Documentation][11]) |
| Step Functions | Standard execution limits: 1 year duration, 25,000 event-history entries, 256 KiB state payload; Distributed Map up to 10,000 child workflows | Confirms external manifest/state storage is required for giant fan-out. ([AWS Documentation][2]) |
| DynamoDB | On-demand is recommended for bursty workloads; max throughput can bound spend but is best-effort | Good fit for session/quota state, with explicit cost guardrails. ([AWS Documentation][12]) |
| AppConfig | Freeform config + validators + staged rollout/deployment strategies; hosted store size limit 2 MB | Best fit for dynamic transfer policy rollout. ([AWS Documentation][13]) |
| SQS | Long polling max 20s; DLQ retention should exceed source queue retention; Standard queues are at-least-once | Best fit for internal large-copy worker lane, if handlers are idempotent. ([AWS Documentation][3]) |
| S3 cost cleanup | Incomplete MPU storage continues billing until complete/abort; Storage Lens exposes incomplete MPU bytes/object counts | Justifies janitor + Storage Lens alarms, not lifecycle alone. ([AWS Documentation][14]) |
| KMS cost posture | S3 Bucket Keys can reduce SSE-KMS request cost by up to 99% | If Nova ever needs SSE-KMS for uploads/exports, Bucket Keys are mandatory. ([AWS Documentation][15]) |

### GitHub repos reviewed

| Repo / doc | Usefulness | Verdict |
| --- | --- | --- |
| `transloadit/uppy` + AWS S3 docs | Strong reference for multipart thresholds, `retryDelays`, chunk sizing, and concurrency caution | Use as heuristic/reference; do not replace Nova’s browser helper now. ([Uppy][16]) |
| `tus/tus-js-client` | Mature resumable-upload protocol/client | Reject for Nova now; would require a new protocol/server surface and violate current S3-native contract. ([GitHub][17]) |
| `alexcasalboni/aws-lambda-power-tuning` | Best benchmark utility for Lambda memory/time tradeoffs | Use to tune copy handlers before setting fan-out threshold. ([GitHub][18]) |
| `aws-powertools/powertools-lambda-python` | Good toolkit for logs/metrics/tracing | Optional only; adopt if it replaces custom glue rather than adding overlap. ([GitHub][19]) |
| `aws-samples/sample-securing-amazon-s3-presigned-urls-for-serverless-applications` | Good reference for checksum + dynamic-expiry presigned URL patterns | Use as implementation evidence, not as architectural dependency. ([GitHub][20]) |

### PyPI packages evaluated

| Package | Assessment | Decision |
| --- | --- | --- |
| `boto3` | Official Python AWS SDK | Keep as primary AWS SDK. ([PyPI][21]) |
| `aioboto3` | Async wrapper around boto3/aiobotocore | Keep existing usage where already present; avoid expanding surface without measured need. ([PyPI][22]) |
| `s3transfer` | AWS-maintained, but package page explicitly says it is not currently GA as a direct production dependency | Do not add directly; prefer stable boto3 interfaces. ([PyPI][23]) |
| `aws-lambda-powertools` | Production-ready serverless helper library | Optional, useful for metrics/tracing/logging standardization. ([PyPI][24]) |

### Infra templates and operational artifacts assessed

Assessed repo truth in:

* `AGENTS.md`
* `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
* `infra/nova_cdk/README.md`
* `infra/nova_cdk/src/nova_cdk/runtime_stack.py`
* `packages/nova_file_api/src/nova_file_api/transfer.py`
* `packages/nova_file_api/src/nova_file_api/routes/transfers.py`
* `packages/nova_file_api/src/nova_file_api/routes/exports.py`
* `packages/nova_runtime_support/src/nova_runtime_support/export_runtime.py`
* `packages/nova_dash_bridge/src/nova_dash_bridge/assets/file_transfer.js`
* `docs/architecture/spec/SPEC-0002-s3-integration.md`
* `SPEC-0003-observability.md`
* `SPEC-0005-abuse-prevention-and-quotas.md`
* `SPEC-0009-caching-and-idempotency.md`
* `SPEC-0027-public-api-v2.md`
* `SPEC-0028-export-workflow-state-machine.md`
* `SPEC-0029-platform-serverless.md`

Conclusion: the repo already has the right macro-architecture. The modernization work is concentrated in transfer policy/state, export copy strategy, and operator guardrails.

---

## 5. Option Set

### 5.1 Upload authorization / resumability pattern

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| U1 | Progressive presigned multipart + durable `UploadSession` | 9.5 | 9.5 | 9.4 | 9.1 | 9.8 | **9.45** | **Adopt** |
| U2 | Scoped temporary STS credentials to browser clients | 8.6 | 9.0 | 8.8 | 7.9 | 8.6 | **8.68** | Reject |
| U3 | tus protocol client/server | 8.0 | 8.6 | 8.4 | 7.0 | 6.8 | **7.92** | Reject |

Rationale:

* U1 fits Nova’s existing contract, preserves least privilege, and fixes the real gaps with minimal API change.
* U2 can reduce request overhead, and Uppy documents speed benefits from temporary security credentials, but it is explicitly a security trade-off and adds STS lifecycle/permission complexity. AWS Prescriptive Guidance also notes temporary credential expiry constraints. ([Uppy][16])
* U3 is technically valid in isolation, but it requires a new server protocol surface and does not fit Nova’s current S3-native public contract. ([GitHub][17])

### 5.2 Network / storage tier for uploads and downloads

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| N1 | General-purpose S3 bucket, Regional endpoint default | 9.5 | 9.4 | 9.5 | 9.2 | 9.9 | **9.47** | **Adopt as default** |
| N2 | Transfer Acceleration, opt-in by policy tier | 9.1 | 9.6 | 8.9 | 8.9 | 9.3 | **9.18** | **Adopt conditionally** |
| N3 | S3 Express One Zone default landing bucket | 7.4 | 9.0 | 7.1 | 6.9 | 6.4 | **7.59** | Reject |
| N4 | Multi-Region Access Point default | 8.3 | 9.1 | 6.7 | 7.7 | 8.0 | **8.05** | Reject |

Rationale:

* N1 is already aligned with Nova’s current contract and requirement set.
* N2 is valuable for long-distance enterprise traffic, but AWS documents extra transfer charges and positions it for centralized buckets with globally distributed users. It should be allow-listed by policy, not universal. ([AWS Documentation][4])
* N3 is rejected because S3 Express One Zone changes the auth/storage model (`CreateSession`, directory buckets, single-AZ durability target) without addressing Nova’s actual bottlenecks. ([Amazon Web Services, Inc.][5])
* N4 is rejected because MRAP adds routing and potential cross-region charges and only makes sense when Nova actually needs a multi-region storage topology. ([Amazon Web Services, Inc.][6])

### 5.3 Dynamic configuration / quota plane

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P1 | Environment variables / CDK only | 8.0 | 8.0 | 9.0 | 9.3 | 9.8 | **8.25** | Reject |
| P2 | DynamoDB config table only | 8.8 | 8.8 | 8.8 | 8.5 | 9.4 | **8.84** | Reject |
| P3 | AppConfig policy profiles + DynamoDB session/usage state + env safety envelope | 9.4 | 9.2 | 9.1 | 9.0 | 9.6 | **9.29** | **Adopt** |

Rationale:

* AppConfig provides staged rollouts, validators, and rollback controls. DynamoDB provides burst handling and authoritative counters/session metadata. The env/CDK layer remains the immutable platform envelope. ([AWS Documentation][13])

### 5.4 Export processing architecture

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| E1 | Inline multipart copy, but with dedicated copy part size/concurrency + cooperative cancel | 9.0 | 9.0 | 9.3 | 9.1 | 9.7 | **9.08** | **Adopt for moderate exports / Phase 1** |
| E2 | Step Functions Standard + internal SQS part-copy worker lane for giant exports | 9.4 | 9.5 | 9.0 | 8.6 | 9.2 | **9.19** | **Adopt for giant exports** |
| E3 | Distributed Map per part/manifest | 9.0 | 9.6 | 8.4 | 7.8 | 8.9 | **8.95** | Reject unless `UNVERIFIED BLOCKER` forces it |

Rationale:

* E1 is a no-regret improvement because the current code mistakenly uses upload tuning for server-side copy tuning.
* E2 is the best giant-export path because it preserves Step Functions as the orchestrator, smooths bursts, and adds replay/DLQ controls.
* E3 is technically powerful, but it adds quota/operational complexity and still requires external manifest/state because of Step Functions payload/history limits. Keep it as contingency only. ([AWS Documentation][2])

### 5.5 Integrity strategy

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| I1 | Current settle-state only (`ListParts` + ETag reconciliation) | 8.5 | 8.8 | 9.5 | 9.4 | 9.8 | **8.84** | Reject as final state |
| I2 | Phased checksum strategy: single PUT checksum now, multipart checksum tiering next | 9.2 | 9.0 | 9.0 | 8.8 | 9.5 | **9.08** | **Adopt** |
| I3 | Mandatory checksum for all browser multipart uploads immediately | 8.9 | 8.7 | 7.8 | 7.9 | 9.2 | **8.59** | Reject |

Rationale:

* AWS supports additional checksum algorithms on SigV4 presigned uploads and multipart checksum modes, but forcing this immediately on giant browser uploads risks CPU/memory regression. Start with a phased model. ([AWS Documentation][9])

### 5.6 Observability and cost guardrails

| Option | Description | A | B | C | D | E | Weighted | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| O1 | Keep current alarms/metrics only | 7.9 | 7.1 | 8.8 | 8.5 | 10.0 | **7.99** | Reject |
| O2 | EMF + Storage Lens + Budgets + janitor telemetry + queue alarms | 9.3 | 8.9 | 9.4 | 9.1 | 9.7 | **9.20** | **Adopt** |
| O3 | High-cardinality object/session metrics everywhere | 8.6 | 8.5 | 5.5 | 6.0 | 9.0 | **7.64** | Reject |

Rationale:

* AWS already exposes the right raw services for this: Storage Lens for incomplete MPUs, EMF/custom metrics for app signals, queue metrics for worker backlogs, and pricing pages/budgets for spend tracking. Use them. Do not emit object-key-cardinality custom metrics. ([AWS Documentation][25])

---

## 6. Decision Matrix

### Final selected architecture

**Selected:** Path B — **High-scale hybrid**, composed of the adopted options above:

1. **Keep direct S3 multipart uploads/downloads as the canonical data plane.**
2. **Add DynamoDB `UploadSession` and `TransferUsageWindow` state.**
3. **Resolve effective transfer policy from AppConfig profiles bounded by immutable platform env/CDK limits.**
4. **Use adaptive upload part sizing and larger signing windows.**
5. **Keep Step Functions Standard for `/v1/exports`, but add an internal large-export SQS worker lane above a measured threshold.**
6. **Keep Transfer Acceleration disabled by default; allow it only for approved remote/enterprise tiers.**
7. **Add phased checksum support, janitor/reconciler flows, and cost/operability guardrails.**

### Selected architecture diagram

```text
Browser / Dash / SDK
|  |
|  |
    v
API Lambda (FastAPI)
|  |
|  |
|  |
|  |
    v
Amazon S3 (direct multipart PUT/GET)
    ^
|  |
|  |
|  |
|  |
|  |
Janitor / Reconciler (scheduled Step Functions + Lambda)

POST /v1/exports
    v
Export record in DynamoDB
    v
Step Functions Standard
|  |
|  |
|  |
|  |
|  |
|  |
|  |
```

### Why this architecture is the best fit

* It solves the stated objective without violating repo truth.
* It keeps Nova’s public contract stable.
* It puts complexity only where current evidence says scale risk is real.
* It preserves least-privilege and cost containment.
* It improves both operator visibility and failure recovery.

### Rejected options

| Option | Why rejected |
| --- | --- |
| Proxy uploads through API Gateway/Lambda/FastAPI | Direct conflict with API Gateway payload limits and Nova’s current control-plane design. ([AWS Documentation][1]) |
| Temporary credentials as default upload auth | Wider permission blast radius and session lifecycle complexity for marginal benefit after sign-batch tuning. ([Uppy][16]) |
| S3 Express One Zone as default upload store | Wrong durability/auth model for Nova’s current contract. ([Amazon Web Services, Inc.][5]) |
| MRAP as default | Adds routing and cross-region cost without a stated multi-region requirement. ([Amazon Web Services, Inc.][6]) |
| Distributed Map as first choice for export part fan-out | Powerful but more operationally complex than necessary for Nova’s current needs. ([AWS Documentation][26]) |
| Uppy Companion / tus server | Violates current browser-only helper boundary and changes the public interaction model. ([Uppy][16]) |

### Decision evidence required before implementation

| Gate | Required evidence | Owner |
| --- | --- | --- |
| Security | Confirm whether SSE-S3 remains acceptable or CMK/SSE-KMS is required; decide checksum policy by client type | Security |
| IAM | Review least-privilege policies for new DDB tables, AppConfig reads, SQS worker lane, and `states:StopExecution` | Infra/Security |
| Billing | Approve TA policy tiers, DDB max-throughput caps, S3 Storage Lens, and budget/alarm thresholds | FinOps |
| Correctness | Benchmark large export copy path to determine inline vs queue threshold; test cancel/abort ambiguity paths | Workflows/API |
| Client UX | Benchmark browser checksum overhead and adaptive concurrency behavior on target browsers/networks | Client/Platform |

---

## 7. Implementation Roadmap

### Phase 0 — Safety baseline

**Goal:** instrument and benchmark before changing behavior.

Completed on `2026-04-03` with `ADR-0042`, the Phase 0 runbook,
`scripts/perf/*`, runtime dashboard IaC, and focused transfer/export/infra
verification.

**Milestones**

* [x] Record ADR for selected architecture.
* [x] Add benchmark harness for:

  * API `initiate` / `sign-parts` throughput,
  * inline export copy handler memory/time,
  * browser upload batch-size behavior.

* [x] Add current-state dashboards for:

  * `initiate`, `sign-parts`, `complete`, `abort`,
  * export queued/copy/finalize age,
  * S3 incomplete MPU bytes/objects older than 7 days,
  * API throttles and reserved-concurrency saturation.

**Dependencies**

* None.

**Acceptance criteria**

* [x] Current 500 GiB upload plan and 1 TiB burst plan documented.
* [x] Copy handler benchmark completed with Power Tuning or equivalent.
* [x] Alarm gaps documented and accepted.

**Tests**

* [x] No contract changes yet.
* [x] Infra synth/tests pass.
* [x] Baseline perf scripts produce repeatable output.

**Rollback**

* N/A; observational only.

### Phase 1 — Contract-safe minimal change

**Goal:** fix the no-regret defects without changing the public model.

**Milestones**

* [x] Add `UploadSession` DynamoDB table.
* [x] Add optional additive fields to initiate response:

  * `session_id`
  * `policy_id`
  * `policy_version`
  * `max_concurrency_hint`
  * `sign_batch_size_hint`
  * `accelerate_enabled`
  * `checksum_algorithm`
  * `resumable_until`
* [x] Add effective policy resolution with env-static fallback.
* [x] Separate upload part size from export copy part size.
* [x] Persist Step Functions execution ARN in export state and implement cooperative cancel with `StopExecution`.

**Dependencies**

* UploadSession table and model.
* Export record schema extension.

**Acceptance criteria**

* [x] Existing clients remain functional with no request-shape breakage.
* [x] Browser helper can use larger sign batches from response/policy hints.
* [x] Cancel actually stops workflow execution for active exports.
* [x] Inline export copy path uses dedicated tuning.

**Tests**

* [x] Unit tests for policy resolution and part-size math.
* [x] Integration tests for initiate/sign/complete with session persistence.
* [x] Export cancel integration tests.
* [x] OpenAPI/SDK regeneration checks pass.

**Rollback**

* [x] Feature-flag dynamic policy resolver off.
* [x] Ignore new response fields in clients.
* [x] Disable `StopExecution` path and fall back to current state-only cancel if needed.

### Phase 2 — Scale hardening

**Goal:** add durable quotas, reconciliation, and operator safeguards.

**Milestones**

* [ ] Add `TransferUsageWindow` counters and conditional quota enforcement.
* [ ] Add scheduled janitor/reconciler workflow for stale sessions, ambiguous completes, repeated aborts, and zombie export MPUs.
* [ ] Add AppConfig profiles and validators for app/workload policy rollout.
* [ ] Add Storage Lens, budgets, and stale-MPU alarms.

**Dependencies**

* AppConfig application/environment/profile/deployment strategy.
* DDB usage table.
* Scheduler / state machine for janitor.

**Acceptance criteria**

* [ ] Quota rejection paths are deterministic and user-visible.
* [ ] Stale sessions expire without waiting for DynamoDB TTL deletion.
* [ ] Incomplete MPU alarms and runbook actions exist.
* [ ] Policy rollout/rollback is tested with AppConfig deployment controls.

**Tests**

* [ ] Quota unit tests with conditional-update conflicts.
* [ ] Janitor integration tests using mocked stale session states.
* [ ] AppConfig schema validation tests.

**Rollback**

* [ ] Disable policy rollout and revert to env/static defaults.
* [ ] Disable janitor schedule.
* [ ] Set quotas to effectively unlimited platform-safe values.

### Phase 3 — Cost/performance optimization and dynamic configuration

**Goal:** add giant-export worker lane and selective acceleration.

**Milestones**

* [ ] Add SQS Standard queue + DLQ + Lambda part-copy workers for giant exports.
* [ ] Add export part state model (`ExportCopyPart` table or manifest+status equivalent).
* [ ] Add two-lane export choice in Step Functions:

  * inline lane for moderate exports,
  * worker lane for giant exports.
* [ ] Add selective TA policy tier.
* [ ] Add phased checksum policy:

  * immediate support for single PUT checksum,
  * optional/required multipart checksum by client class.

**Dependencies**

* Benchmarked threshold for queue lane activation (`UNVERIFIED BLOCKER` until measured).
* Worker idempotency model.

**Acceptance criteria**

* [ ] Giant export path survives retry/duplication without corruption.
* [ ] Queue backlog, DLQ, and cancel semantics are observable.
* [ ] TA can be enabled per policy without affecting default path.
* [ ] Sign requests per 500 GiB upload are reduced materially from current baseline.

**Tests**

* [ ] Worker idempotency tests.
* [ ] Export partial-failure replay tests.
* [ ] Contract tests for new policy/capability surface.
* [ ] Perf tests for giant-upload and giant-export tiers.

**Rollback**

* [ ] Set giant-export threshold above any real workload so all exports stay inline.
* [ ] Disable TA in policy profiles.
* [ ] Disable checksum-required tiers.

### Phase 4 — Validation and rollout

**Goal:** controlled production adoption.

**Milestones**

* [ ] Canary rollout by app/workload profile.
* [ ] Update runbooks, docs, SDKs, dashboards, and alarms.
* [ ] Update deploy-output artifacts/schema if new outputs are required by validation tooling.
* [ ] Post-deploy validation with representative giant-upload and export scenarios.

**Dependencies**

* All previous phases.

**Acceptance criteria**

* [ ] No public contract regression.
* [ ] Error/throttle/cost alarms stable after rollout.
* [ ] Rollback tested and documented.
* [ ] Release provenance remains deploy-output-authoritative.

**Tests**

* [ ] Full CI gates.
* [ ] Post-deploy synthetic upload/export validation.
* [ ] Budget alarm smoke tests.

**Rollback**

* [ ] Revert AppConfig profiles to prior versions.
* [ ] Raise giant-export threshold to force inline only.
* [ ] Disable new routes/fields behind feature flags if needed.

---

## 8. Detailed technical plan

### 8.1 API and configuration changes

**Keep existing public routes. Add only additive contract surface.**

**Recommended additive fields**

* `InitiateUploadRequest`

  * `workload_class: str | None`
  * `policy_hint: str | None`
  * `checksum_preference: Literal["none","standard","strict"] | None`
* `InitiateUploadResponse`

  * `session_id: str`
  * `policy_id: str`
  * `policy_version: str`
  * `max_concurrency_hint: int`
  * `sign_batch_size_hint: int`
  * `accelerate_enabled: bool`
  * `checksum_algorithm: str | None`
  * `resumable_until: datetime`
* `UploadIntrospectionResponse`

  * optional `session_status`
  * optional `resumable_until`

**New capability/policy route**

* `GET /v1/capabilities/transfers`

  * Returns effective policy for the caller’s app/workload context.
  * Optional query parameter: `workload_class`.
  * This is cleaner than overloading `/v1/resources/plan`.

**Policy resolution order**

1. Platform envelope from env/CDK (hard upper/lower bounds; immutable at runtime)
2. AppConfig profile by environment/app/workload tier
3. Optional scope override (if Nova needs tenant-specific override later)
4. Per-request hint that can only narrow/select an allowed profile, never raise limits

**Recommended policy schema**

```json
{
  "policy_id": "enterprise-giant-v1",
  "max_upload_bytes": 536870912000,
  "multipart_threshold_bytes": 104857600,
  "target_upload_part_count": 2000,
  "min_part_size_bytes": 134217728,
  "max_part_size_bytes": 536870912,
  "max_client_concurrency": 8,
  "sign_batch_size": 64,
  "presign_upload_ttl_seconds": 1800,
  "allow_transfer_acceleration": true,
  "checksum_mode": "optional",
  "active_multipart_limit": 200,
  "daily_ingress_budget_bytes": 1099511627776,
  "max_uncommitted_signed_parts": 256,
  "export_copy_part_size_bytes": 2147483648,
  "export_copy_max_concurrency": 8,
  "large_export_worker_threshold_bytes": 53687091200,
  "retry_profile": {
    "part_attempts": 5,
    "base_delay_ms": 250,
    "max_delay_ms": 5000,
    "jitter": "full"
  }
}
```

AppConfig is the correct rollout surface for this because it supports freeform config, validators, staged deployment strategies, and rollback with alarms. Hosted config size limits are not a blocker for this schema. ([AWS Documentation][13])

### 8.2 Runtime and workflow changes

#### Upload path

**Initiate**

* Resolve effective policy.
* Compute adaptive part size:

  * `upload_part_size = clamp(ceil(size_bytes / target_upload_part_count), min_part_size, max_part_size)`
* Create `UploadSession`.
* Conditionally increment usage counters.
* Create MPU in S3 and return hints.

**Recommended upload part-size rule**

```text
upload_part_size =
  clamp(
    ceil(file_size_bytes / target_upload_part_count),
    64 MiB,
    512 MiB
  )
```

For Nova’s target profile:

* 500 GiB upload at 256 MiB parts → ~2,000 parts
* 500 GiB upload at 512 MiB parts → ~1,000 parts

That is a much better control-plane shape than the current static 128 MiB / 4,000-part path.

**Sign parts**

* Validate session is alive and owned by caller.
* Enforce `max_uncommitted_signed_parts`.
* Update `last_activity_at`.
* Return batched presigned URLs.

**Recommended signing-window rule**

```text
sign_batch_size =
  clamp(
    max(4 * max_client_concurrency, 32),
    32,
    128
  )
```

**Introspect**

* Keep S3 `ListParts` as the authoritative part inventory.
* Do **not** mirror every completed part into DynamoDB; that would create unnecessary write amplification and item-size risk.
* Update session heartbeat only.

**Complete**

* Keep current `ListParts` + ETag validation.
* Mark session `completed` only after S3 complete succeeds.
* If client loses the response after completion, mark state `ambiguous`, reconcile via `HeadObject`, then settle.

**Abort**

* Mark session `aborting`.
* Call `AbortMultipartUpload`.
* Re-check later if in-flight parts may still have landed; AWS documents that abort may need to be retried to fully free storage. ([AWS Documentation][27])

#### Export path

**Immediate fix**

* Add dedicated export copy tuning:

  * `export_copy_part_size_bytes`
  * `export_copy_max_concurrency`
* Do not reuse upload part size for server-side copy.

**Recommended copy-part rule**

```text
copy_part_size =
  clamp(
    ceil(object_size_bytes / target_copy_part_count),
    1 GiB,
    5 GiB
  )
```

For server-side copy, large parts are desirable because there is no public-network retransmission penalty.

**Two-lane export strategy**

* `<= 5 GB`: use `CopyObject`
* `> 5 GB` and under measured threshold: inline multipart copy Lambda
* `> threshold`: queue-backed part-copy worker lane

**Large-export worker lane**

* Step Functions creates export MPU and manifest reference.
* One SQS message per copy range.
* Worker Lambda executes `UploadPartCopy`.
* Worker writes `{export_id, part_number, etag, status}` idempotently.
* Finalize task completes MPU from persisted part state.
* Cancel path sets `cancel_requested_at`; workers check export state before each part.
* Fail path aborts MPU and drains/ignores remaining work.

SQS is a better burst smoother here than per-part state transitions inside Step Functions. Step Functions still orchestrates the workflow; SQS only absorbs internal copy pressure. Long polling, DLQs, and idempotent handlers are the required operational baseline. ([AWS Documentation][3])

### 8.3 Data model and schema updates

#### `UploadSession` table

**Partition key:** `session_id`
**Recommended GSIs:**

* `scope_id-status-updated_at`
* `upload_id`
* optional `policy_id-updated_at`

**Fields**

* `session_id`
* `upload_id`
* `scope_id`
* `app_id`
* `workload_class`
* `bucket`
* `key`
* `filename`
* `size_bytes`
* `content_type`
* `strategy`
* `part_size_bytes`
* `checksum_algorithm`
* `accelerate_enabled`
* `policy_id`
* `policy_version`
* `status`
* `created_at`
* `last_activity_at`
* `resumable_until`
* `expires_at`
* `request_id`

#### `TransferUsageWindow` table

**Key idea:** enforce coarse-grained quotas, not per-part accounting.

**Partition key example:** `scope_id#YYYYMMDDHH`
**Sort key example:** `metric#shard`

**Counters**

* `bytes_initiated`
* `bytes_completed`
* `active_sessions`
* `sign_requests`
* `quota_rejections`

Use on-demand mode with max throughput configured to bound surprise cost, understanding that the cap is best-effort because burst capacity can temporarily exceed it. That is acceptable as a secondary control, not as the only guardrail. ([AWS Documentation][28])

#### Export record extension

Add:

* `execution_arn`
* `cancel_requested_at`
* `copy_strategy`
* `copy_part_size_bytes`
* `copy_started_at`
* `last_heartbeat_at`
* optional `manifest_ref`

Optional new table if queue lane is adopted:

* `ExportCopyPart(export_id, part_number)`

### 8.4 State and idempotency hardening

* Reuse current guarded mutation/idempotency model for:

  * initiate
  * complete
  * abort
  * create export
  * cancel export
* Enforce state transitions with conditional writes:

  * `initiated -> uploading -> completing -> completed`
  * `initiated/uploading/completing -> aborting -> aborted`
* Do not rely on DynamoDB TTL deletion timing for correctness. Repo specs already treat TTL as eventual; the application must enforce expiry itself.
* Use S3 as authority for part inventory; use DynamoDB as authority for session state and quota state.
* Treat S3 Event Notifications only as optional hints/triggers because delivery is at-least-once and may be duplicated or out of order. ([AWS Documentation][29])

### 8.5 Observability and alarms

**API metrics**

* `uploads_initiated_total`
* `uploads_sign_parts_total`
* `uploads_complete_total`
* `uploads_abort_total`
* `uploads_resume_total`
* `uploads_ambiguous_complete_total`
* p50/p95/p99 latency for initiate/sign/introspect/complete
* API Gateway 429/5xx
* Lambda throttles/errors/duration/max memory

**Session metrics**

* `upload_sessions_active`
* `upload_sessions_stale`
* `upload_sessions_expired`
* `quota_rejections_total`
* `signed_parts_outstanding`
* `sign_requests_per_upload`

**Export metrics**

* `exports_queued_age_ms`
* `exports_copying_age_ms`
* `exports_cancel_lag_ms`
* `export_copy_worker_failures_total`
* `export_copy_dlq_depth`
* `export_copy_retries_total`

**Cost / storage metrics**

* Storage Lens:

  * `IncompleteMPUStorageBytes`
  * `IncompleteMPUObjectCount`
  * `IncompleteMPUStorageBytesOlderThan7Days`
* TA bytes by policy tier
* DynamoDB read/write spikes
* Step Functions state transitions and `ExecutionThrottled`

**Alarms**

* [ ] API Lambda throttles > 0
* [ ] API Gateway 429/5xx above threshold
* [ ] Upload session stale count above threshold
* [ ] Incomplete MPU bytes older than 7 days above threshold
* [ ] Export queue DLQ depth > 0
* [ ] Step Functions failed/timed out/throttled
* [ ] DynamoDB throttled requests > 0
* [ ] TA spend anomaly / budget breach
* [ ] KMS request anomaly if SSE-KMS is enabled

Use structured logs + correlation IDs + EMF-style metrics. The uploaded repo guidance is already explicit on this.

### 8.6 IAM policy boundary updates

**API Lambda**

* Add read/write access to:

  * `UploadSession` table
  * `TransferUsageWindow` table
* Add AppConfig data-plane read actions if runtime fetches policy dynamically
* Keep current S3 prefix-scoped permissions
* Add `states:StopExecution` for export cancel

**Workflow / worker Lambdas**

* Add SQS receive/delete/change-visibility permissions
* Add DDB write permissions to export part/session tables as needed
* Keep S3 MPU copy/abort permissions scoped to upload/export prefixes

**AppConfig**

* Runtime needs only read-path permissions.
* Admin/deploy pipeline owns write/deploy permissions.

**Encryption**

* Keep SSE-S3 by default.
* If CMK/SSE-KMS becomes required, add S3 Bucket Keys immediately to avoid KMS request explosion. ([AWS Documentation][15])

### 8.7 CDK and template updates

In `infra/nova_cdk/src/nova_cdk/runtime_stack.py`:

* [ ] Add `UploadSession` table
* [ ] Add `TransferUsageWindow` table
* [ ] Add SQS queue + DLQ + event source mapping for giant export worker lane
* [ ] Add AppConfig resources or references
* [ ] Add CloudWatch alarms/dashboards for new metrics
* [ ] Add runtime env/config contract fields
* [ ] Extend IAM grants
* [ ] Extend deploy outputs only if post-deploy validation needs new resource identifiers

### 8.8 SDK impact and regeneration points

Any additive field/route change means:

* [ ] update OpenAPI source
* [ ] regenerate TS SDK
* [ ] regenerate Python SDK
* [ ] regenerate R artifacts if affected
* [ ] update Dash/browser integration docs
* [ ] update contract tests and generated smoke tests

Required repo gates are already clear in `AGENTS.md`. Keep fixes at the source of truth, not in generated artifacts.

---

## 9. Checklists

### Requirements checklist

* [x] Confirm current Nova authoritative docs and current architecture truth in one run.
* [x] Collect and validate latest source links (official, current, not stale).
* [x] Map current bottlenecks in API, S3 multipart, orchestration, workflow fanout, export state storage, and config model.
* [x] Produce at least 3 competing architectural options per major design area.
* [x] Score each major option with weighted formula; discard `< 9.0` final candidates.
* [x] Produce a full migration path for large file + high concurrency without breaking public Nova contract.
* [x] Design dynamic config surface with secure boundaries and compatibility policy.
* [x] Define failure modes + retries + backoff + dead-lettering + replay strategy.
* [x] Include cost/performance model assumptions and benchmark plan.
* [x] Define observability and alarms before/after change.
* [x] List missing tests/docs/templates/contract updates required.
* [x] Produce phase-by-phase rollout and rollback plan.

### Implementation subtasks with owners

**Platform / API**

* [x] Add `UploadSession` repository/model/service hooks — **Owner: API Platform**
* [x] Add effective policy resolver and capability route — **Owner: API Platform**
* [x] Add adaptive part sizing and sign-batch hints — **Owner: API Platform**
* [ ] Add quota enforcement on initiate/sign — **Owner: API Platform**
* [x] Add checksum policy fields and validation — **Owner: API Platform**

**Workflows**

* [x] Persist export execution ARN and cooperative cancel — **Owner: Workflow Platform**
* [x] Add dedicated inline export copy tuning — **Owner: Workflow Platform**
* [ ] Implement giant export worker lane — **Owner: Workflow Platform**
* [ ] Add janitor/reconciler workflow — **Owner: Workflow Platform**

**Infra / CDK**

* [x] Provision DDB tables, queues, alarms, IAM updates — **Owner: Infra**
* [ ] Add AppConfig resources or bindings — **Owner: Infra**
* [x] Update deploy-output and infra contract tests if needed — **Owner: Infra**

**SDK / Clients / Docs**

* [x] Regenerate OpenAPI and SDKs — **Owner: SDK**
* [x] Update `nova_dash_bridge` docs/examples — **Owner: Client Platform**
* [x] Update runbooks and active docs — **Owner: Docs / Platform**

**Observability / FinOps / Security**

* [ ] Add Storage Lens and budget alarms — **Owner: FinOps**
* [ ] Review IAM least privilege and encryption tier — **Owner: Security**
* [ ] Validate checksum policy and presigned URL guardrails — **Owner: Security + Client Platform**

### Verification checklist by layer

**API**

* [x] Initiate returns additive fields only
* [x] Old clients ignore new fields
* [x] Policy resolution falls back safely when AppConfig unavailable
* [ ] Quota-exceeded errors are deterministic

**Workflow**

* [x] Cancel stops active executions
* [ ] Queue workers are idempotent
* [ ] DLQ handling and replay tested
* [ ] Janitor resolves stale/ambiguous sessions safely

**Infra**

* [x] CDK synth stable
* [x] IAM diff reviewed
* [ ] New alarms/dashboards deployed
* [x] deploy-output remains authoritative

**SDK / Contracts**

* [x] OpenAPI diff reviewed
* [x] TS/Python/R clients regenerate cleanly
* [x] Generated smoke tests pass

**Cost / Performance**

* [ ] Sign requests per giant upload materially reduced
* [ ] No unexpected DDB throttle or spend spikes
* [ ] TA only active on allow-listed profiles
* [ ] Incomplete MPU bytes older than 7 days within target

---

## 10. Success Criteria

### Latency / throughput targets

* `initiate` p95 `< 250 ms`
* `sign-parts` p95 `< 400 ms`
* `introspect` p95 `< 1 s` for 4,000-part uploads
* `complete` p95 `< 2 s` excluding downstream client retries
* 500 GiB single-file upload supported end-to-end
* 1 TiB aggregate burst supported without API 5xx/throttle events in staging
* Giant upload policy yields **1,000–2,000 parts per 500 GiB file**, not 4,000

### Failure recovery targets

* Resume after browser refresh/network interruption without re-upload of already confirmed parts
* Ambiguous complete state reconciled automatically
* Cancel propagation to workflow `< 60 s`
* Stale MPU/session reconciliation `< 2 h` after expiry
* No orphaned giant export MPU after janitor run

### Cost / cost-per-GB targets

Absolute `$ / GB` targets are **UNVERIFIED** until region, egress mix, and encryption tier are fixed.

Use these operational cost targets instead:

* Reduce `sign-parts` control-plane calls per 500 GiB browser upload by **> 80%** versus current default path
* Keep incomplete MPU bytes older than 7 days `< 0.5%` of monthly ingress bytes
* Keep TA bytes at **0 by default** and only non-zero on allow-listed policy tiers
* If SSE-KMS is required later, Bucket Keys must be enabled from day 1 of that migration

### Contract / test stability gates

* No breaking request-shape changes
* All new fields/routes additive only
* OpenAPI/SDK/docs/tests updated in same release train
* No decision adopted with weighted score `< 9.0`

---

## 11. Command / CI plan

### Blocking gates (current repo-native)

```bash
uv sync --locked --all-packages --all-extras --dev
uv lock --check
uv run ruff check .
uv run ruff check . --select I
uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q -m runtime_gate
uv run pytest -q -m "not runtime_gate and not generated_smoke"
uv run pytest -q -m generated_smoke
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
bash scripts/checks/run_infra_contracts.sh
```

### Recommended additional blocking gates to add

```bash
uv run pytest -q packages/nova_file_api/tests/test_transfer_policy_resolution.py
uv run pytest -q packages/nova_file_api/tests/test_upload_session_repository.py
uv run pytest -q packages/nova_file_api/tests/test_export_cancel_stop_execution.py
uv run pytest -q packages/nova_workflows/tests/test_export_copy_worker_idempotency.py
uv run pytest -q tests/infra/test_runtime_stack_transfer_scaling_resources.py
```

### Recommended non-blocking but required before production rollout

```bash
uv run python scripts/perf/benchmark_transfer_control_plane.py
uv run python scripts/perf/benchmark_export_copy.py
uv run python scripts/perf/benchmark_browser_upload_matrix.py
npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" ...
```

### How to verify

* Ruff passes with no formatting or import drift.
* `ty` and `mypy` pass.
* Existing runtime and generated smoke suites pass.
* OpenAPI/runtime-config generation checks pass.
* Infra contract tests pass.
* Perf scripts show:

  * reduced sign-call counts,
  * acceptable API p95 latency,
  * measured threshold for queue-backed export lane.

---

## 12. Risk Register

| Risk | Severity | Likelihood | Mitigation |
| --- | --- | --- | --- |
| Wrong threshold for switching export copy to worker lane | High | Medium | Benchmark inline copy first; keep threshold feature-flagged; start conservative |
| DDB usage-window hot partition under one massive tenant | Medium | Medium | Use hourly buckets; add shard suffix if needed; monitor throttles |
| AppConfig bad rollout blocks uploads | High | Low-medium | Validators + staged rollout + alarm rollback + env fallback |
| Browser checksum requirement harms UX | Medium | Medium | Phase checksum policy; benchmark target browsers first |
| TA spend overruns | Medium | Medium | Default off; allow-list tiers only; budget alarms |
| Queue duplicates corrupt export | High | High | Idempotent worker keyed by `{export_id, part_number}`; finalization from persisted latest ETags |
| Janitor accidentally aborts active uploads | High | Low | Expiry based on `last_activity_at`, session state, and grace windows; dry-run mode first |
| Export cancel races with worker completion | Medium | Medium | Workers check cancel flag before each part and finalizer rechecks state |
| SSE-KMS adoption causes request-cost shock | Medium | Medium | Keep SSE-S3 unless required; if required, enable Bucket Keys immediately |
| Step Functions payload/history exhaustion | Medium | Low | Keep manifests outside execution payload; pass only references |

---

## 13. Complete URL list

### AWS documentation

```text
https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration-getting-started.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance-design-patterns.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-express-authenticating-authorizing.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-express-performance.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/MultiRegionAccessPoints.html
https://docs.aws.amazon.com/AmazonS3/latest/userguide/MultiRegionAccessPointRestrictions.html
https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-execution-service-limits-table.html
https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html
https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html
https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html
https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html
https://docs.aws.amazon.com/step-functions/latest/dg/state-map.html
https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html
https://docs.aws.amazon.com/step-functions/latest/dg/sfn-best-practices.html
https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html
https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html
https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode-max-throughput.html
https://docs.aws.amazon.com/appconfig/latest/userguide/what-is-appconfig.html
https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile-about-hosted-store.html
https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile-validators.html
https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-deploying.html
https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-deployment-strategy.html
https://docs.aws.amazon.com/appconfig/latest/userguide/about-data-plane.html
https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-integration-lambda-extensions.html
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-short-and-long-polling.html
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/best-practices-setting-up-long-polling.html
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/setting-up-dead-letter-queue-retention.html
https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html
https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/overview.html
https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/additional-guardrails.html
https://docs.aws.amazon.com/powertools/python/latest/
```

### AWS pricing and FAQs

```text
https://aws.amazon.com/s3/pricing/
https://aws.amazon.com/step-functions/pricing/
https://aws.amazon.com/dynamodb/pricing/
https://aws.amazon.com/lambda/pricing/
https://aws.amazon.com/s3/faqs/
```

### AWS blogs / implementation references

```text
https://aws.amazon.com/blogs/compute/securing-amazon-s3-presigned-urls-for-serverless-applications/
https://aws.amazon.com/blogs/compute/patterns-for-building-an-api-to-upload-files-to-amazon-s3/
https://aws.amazon.com/blogs/compute/uploading-large-objects-to-amazon-s3-using-multipart-upload-and-transfer-acceleration/
```

### GitHub / OSS references

```text
https://uppy.io/docs/aws-s3/
https://github.com/transloadit/uppy
https://github.com/tus/tus-js-client
https://tus.io/
https://github.com/alexcasalboni/aws-lambda-power-tuning
https://github.com/aws-powertools/powertools-lambda-python
https://github.com/aws-samples/sample-securing-amazon-s3-presigned-urls-for-serverless-applications
https://github.com/aws-samples/generate-s3-accelerate-presigned-url
```

### PyPI package references

```text
https://pypi.org/project/boto3/
https://pypi.org/project/aioboto3/
https://pypi.org/project/s3transfer/
https://pypi.org/project/aws-lambda-powertools/
```

---

**Decisions finalized (>=9.0):** direct S3 multipart remains canonical upload/download plane; AppConfig + DynamoDB effective policy model; `UploadSession` + `TransferUsageWindow` tables; adaptive upload part sizing and larger sign windows; dedicated inline export copy tuning; queue-backed giant-export worker lane under Step Functions; cooperative export cancel with `StopExecution`; phased checksum strategy; EMF + Storage Lens + budget/queue alarms; SSE-S3 default with Bucket Keys mandated if SSE-KMS is introduced.

**Open Items:** Security — confirm SSE-S3 vs SSE-KMS and checksum tiering; FinOps — approve TA policy tiers and DDB max-throughput caps; Workflow Platform — benchmark threshold for switching from inline copy to worker lane; Client Platform — decide whether cross-device resume needs a server-assisted recovery route.

**UNVERIFIED assumptions:** dominant upload pattern is internet/browser to one regional bucket; no current compliance requirement forces SSE-KMS/CMK; giant export SLA has not yet been fixed; browser-side multipart checksum cost on target browsers is not yet benchmarked; queue-lane activation threshold for giant exports is not yet measured.

**Next action:** 1) **API Platform** — add `UploadSession` + policy resolver skeleton and wire additive response fields; 2) **Workflow Platform** — separate export copy tuning from upload tuning and persist execution ARN for cooperative cancel; 3) **Infra** — add CDK definitions for new DDB tables, AppConfig profile, and the first new alarms/dashboards.

[1]: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-execution-service-limits-table.html "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-execution-service-limits-table.html"
[2]: https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html "https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html"
[3]: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-short-and-long-polling.html "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-short-and-long-polling.html"
[4]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html"
[5]: https://aws.amazon.com/s3/faqs/ "https://aws.amazon.com/s3/faqs/"
[6]: https://aws.amazon.com/s3/pricing/ "https://aws.amazon.com/s3/pricing/"
[7]: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html"
[8]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html"
[9]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html"
[10]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html"
[11]: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html "https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html"
[12]: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html"
[13]: https://docs.aws.amazon.com/appconfig/latest/userguide/what-is-appconfig.html "https://docs.aws.amazon.com/appconfig/latest/userguide/what-is-appconfig.html"
[14]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html"
[15]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html"
[16]: https://uppy.io/docs/aws-s3/ "https://uppy.io/docs/aws-s3/"
[17]: https://github.com/tus/tus-js-client "https://github.com/tus/tus-js-client"
[18]: https://github.com/alexcasalboni/aws-lambda-power-tuning "https://github.com/alexcasalboni/aws-lambda-power-tuning"
[19]: https://github.com/aws-powertools/powertools-lambda-python "https://github.com/aws-powertools/powertools-lambda-python"
[20]: https://github.com/aws-samples/sample-securing-amazon-s3-presigned-urls-for-serverless-applications "https://github.com/aws-samples/sample-securing-amazon-s3-presigned-urls-for-serverless-applications"
[21]: https://pypi.org/project/boto3/ "https://pypi.org/project/boto3/"
[22]: https://pypi.org/project/aioboto3/ "https://pypi.org/project/aioboto3/"
[23]: https://pypi.org/project/s3transfer/ "https://pypi.org/project/s3transfer/"
[24]: https://pypi.org/project/aws-lambda-powertools/ "https://pypi.org/project/aws-lambda-powertools/"
[25]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html"
[26]: https://docs.aws.amazon.com/step-functions/latest/dg/state-map.html "https://docs.aws.amazon.com/step-functions/latest/dg/state-map.html"
[27]: https://docs.aws.amazon.com/AmazonS3/latest/API/API_AbortMultipartUpload.html "https://docs.aws.amazon.com/AmazonS3/latest/API/API_AbortMultipartUpload.html"
[28]: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode-max-throughput.html "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode-max-throughput.html"
[29]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html "https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html"
