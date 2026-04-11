# Nova architecture requirements

Status: Active
Repository state: **current implemented AWS-native serverless baseline**
Last reviewed: 2026-04-10

## Purpose

Define the active architectural requirements for Nova as it exists now. This
file is current-state authority and the stable traceability ledger for active
and archived ADR/SPEC links.

## Functional requirements

Traceability note: stable requirement IDs are preserved even when earlier
draft wording has been simplified or reinterpreted to match the current
baseline. Older archived ADRs/SPECs may still link these anchors.

<a id="fr-0000-file-transfer-control-plane-endpoints"></a>
### FR-0000 File transfer control-plane endpoints

Nova remains a control plane for direct-to-S3 upload and download flows under
`/v1/transfers/*`; it does not proxy bulk bytes through the API runtime.

<a id="fr-0001-async-job-endpoints-and-orchestration"></a>
### FR-0001 Async job endpoints and orchestration

Asynchronous work remains explicit export workflow orchestration under
`/v1/exports*`; generic public jobs APIs and callback-style workflow semantics
must not return.

<a id="fr-0002-operational-endpoints"></a>
### FR-0002 Operational endpoints

Operational routes remain explicit and limited to the supported `/v1/*`
capability and health surface plus `/metrics/summary`.

<a id="fr-0003-key-generation-and-scope-enforcement"></a>
### FR-0003 Key generation and scope enforcement

Runtime-generated object keys, transfer scope boundaries, and downstream
resource references must remain deterministic and authorization-aware.

<a id="fr-0004-idempotency-for-mutation-entrypoints"></a>
### FR-0004 Idempotency for mutation entrypoints

Mutation entrypoints that need replay protection must keep durable
idempotency/state in DynamoDB rather than ephemeral caches.

<a id="fr-0005-authentication-and-authorization"></a>
### FR-0005 Authentication and authorization

Public authentication remains bearer JWT only, verified in process by the
FastAPI runtime. Session auth, same-origin auth, and a separate auth service
are not active surfaces.

<a id="fr-0006-two-tier-caching"></a>
### FR-0006 Two-tier caching

Any optional cache layer must remain non-authoritative. Correctness,
idempotency, and workflow state stay in durable systems of record; Redis-backed
correctness paths are out of scope.

<a id="fr-0007-observability-and-analytics"></a>
### FR-0007 Observability and analytics

The runtime must continue to expose operator-relevant health, metrics,
dashboard, alarm, and transfer-budget evidence for deploy validation and live
operations.

<a id="fr-0008-openapi-contract-ownership"></a>
### FR-0008 OpenAPI contract ownership

OpenAPI remains the source of truth for the public API contract and generated
client surfaces. The reduced public artifact is the SDK generation authority.

<a id="fr-0009-s3-multipart-correctness-and-acceleration-compatibility"></a>
### FR-0009 S3 multipart correctness and acceleration compatibility

Multipart upload/session state, checksum posture, and policy-controlled
Transfer Acceleration compatibility must remain explicit runtime contracts.

<a id="fr-0011-downstream-hard-cut-consumer-integration-contract"></a>
### FR-0011 Downstream hard-cut consumer integration contract

Downstream consumer docs and examples must point at the surviving SDK,
browser-bridge, and reusable validation surfaces only.

<a id="fr-0012-auth0-tenant-ops-reusable-workflow-contract"></a>
### FR-0012 Auth0 tenant-ops reusable workflow contract

Auth0 tenant bootstrap, audit, and deploy automation must stay bound to the
shared template, reusable workflow API, and repo-owned tooling.

<a id="fr-0013-ssm-runtime-base-url-authority-for-deploy-validation"></a>
### FR-0013 Deploy-output runtime base URL authority for deploy validation

Deploy validation must consume one machine-readable runtime authority. In the
current baseline that published authority is `deploy-output.json`; runtime
config parameters support deployment assembly, not free-text public base URL
override workflows.

## Global functional requirements

<a id="gfr-r1--single-public-runtime-authority"></a>
### GFR-R1 Single public runtime authority

The Regional REST API custom domain recorded in `deploy-output.json` is the
only intended public runtime authority when that artifact exists.

<a id="gfr-r2--auth-context-comes-from-verified-claims"></a>
### GFR-R2 Auth context comes from verified claims

Runtime auth context must derive from verified bearer-token claims, not from
session identifiers, client-provided scopes, or ambient same-origin state.

<a id="gfr-r3--async-correctness-is-mandatory"></a>
### GFR-R3 Async correctness is mandatory

Workflow state transitions, cancellations, retries, and poison recovery must
remain durable, explicit, and deterministic.

<a id="gfr-r4--public-contract-must-be-explicit"></a>
### GFR-R4 Public contract must be explicit

The public route, auth, and error surface must remain literal and typed; no
retired alias surface should quietly persist.

<a id="gfr-r5--worker-must-not-self-call-the-api"></a>
### GFR-R5 Worker must not self-call the API

Workflow tasks and worker lanes must operate on domain/state primitives
directly rather than re-entering the public API as an internal transport.

<a id="gfr-r6--sdks-must-feel-native-per-language"></a>
### GFR-R6 SDKs must feel native per language

Generated or thin client surfaces must match language-native expectations and
avoid unnecessary repo-local runtime wrappers.

<a id="gfr-r7--managed-aws-services-preferred"></a>
### GFR-R7 Managed AWS services preferred

Prefer AWS-managed serverless primitives that fit Nova's control-plane shape
over heavier always-on infrastructure.

<a id="gfr-r8--one-client-artifact-family-per-language"></a>
### GFR-R8 One client artifact family per language

Nova keeps one package family per language; split auth/file client families and
parallel transport packages are not active.

<a id="gfr-r9--deterministic-build-and-verification"></a>
### GFR-R9 Deterministic build and verification

Generated artifacts, contract checks, and release evidence must remain
deterministic from committed repo sources.

<a id="gfr-r10--repo-should-shrink-after-every-accepted-branch"></a>
### GFR-R10 Repo should shrink after every accepted branch

Accepted cleanup work should converge on one canonical implementation and
delete superseded paths, docs, and compatibility layers instead of preserving
parallel surfaces.

## Non-functional requirements

<a id="nfr-0000-security-baseline"></a>
### NFR-0000 Security baseline

Security-sensitive surfaces must fail closed on missing or inconsistent auth,
IAM, runtime ingress, and release wiring.

<a id="nfr-0001-performance-and-event-loop-safety"></a>
### NFR-0001 Performance and event-loop safety

Runtime request handling, auth verification, and orchestration helpers must
remain event-loop-safe and avoid unnecessary blocking work on the hot path.

<a id="nfr-0002-scalability-and-resilience"></a>
### NFR-0002 Scalability and resilience

The deployed system must stay compatible with bursty control-plane traffic,
durable workflow execution, and selective reserved-concurrency protections.

<a id="nfr-0003-operability"></a>
### NFR-0003 Operability

Operators must retain actionable health, alarm, dashboard, budget, and release
evidence without relying on ad hoc local shell state.

<a id="nfr-0004-cicd-and-quality-gates"></a>
### NFR-0004 CI/CD and quality gates

Repo-native lint, typing, test, generator, and infra contract gates remain
authoritative and deterministic.

<a id="nfr-0105-contract-traceability"></a>
### NFR-0105 Contract traceability

Requirements, ADRs, specs, runbooks, contracts, and tests must remain linked
through durable identifiers or explicit source references.

<a id="nfr-0106-no-shim-posture"></a>
### NFR-0106 No shim posture

Retired deploy, auth, SDK, and infrastructure surfaces should be deleted or
archived instead of maintained behind compatibility shims.

<a id="nfr-0107-downstream-contract-doc-and-schema-synchronization"></a>
### NFR-0107 Downstream contract doc and schema synchronization

Downstream validation/workflow docs must stay synchronized with reusable
workflow inputs, outputs, and contract schemas.

<a id="nfr-0108-auth0-workflow-contract-synchronization"></a>
### NFR-0108 Auth0 workflow contract synchronization

Auth0 reusable workflow docs, schemas, and automation surfaces must evolve in
the same change set when behavior changes.

<a id="nfr-0109-runtime-base-url-integrity-and-provenance"></a>
### NFR-0109 Runtime base URL integrity and provenance

Published runtime authority must bind public base URL, release identity, and
stack provenance into one verifiable artifact.

<a id="nfr-0110-architecture-authority-synchronization"></a>
### NFR-0110 Architecture authority synchronization

Active docs must describe implemented state, not target-state aspiration, and
historical planning material must stay off the active authority path.

## Implementation requirements

<a id="ir-0000-nova-local-runtime-and-release-authority"></a>
### IR-0000 Nova local runtime and release authority

`infra/nova_cdk` remains the canonical infrastructure path, and the AWS-native
release control plane remains the only supported post-merge publish/promote/
deploy executor.

<a id="ir-0001-sidecar-routing-model"></a>
### IR-0001 Sidecar routing model

Legacy sidecar routing assumptions are not active. The current runtime uses one
FastAPI/Lambda entrypoint plus explicit workflow/task packages.

<a id="ir-0002-aws-service-dependencies"></a>
### IR-0002 AWS service dependencies

The canonical deployed system depends on API Gateway, Lambda, Step Functions,
DynamoDB, S3, CloudWatch, AppConfig, SNS, SQS, EventBridge, and Route 53 as
documented by the active platform/runbook authority.

<a id="ir-0003-optional-remote-auth-service"></a>
### IR-0003 Optional remote auth service

A separate remote auth service is not part of the active implementation and
must not be reintroduced as a hidden dependency.

<a id="ir-0004-browser-compatibility-for-multipart-workflows"></a>
### IR-0004 Browser compatibility for multipart workflows

Browser upload flows must keep additive initiate hints, bearer-header DOM
contract wiring, and capability-envelope discovery compatible with the current
`nova_dash_bridge` surface.

<a id="ir-0011-cross-repo-consumer-conformance-authority"></a>
### IR-0011 Cross-repo consumer conformance authority

Consumer repos must derive deploy validation and runtime authority from
Nova-owned schemas, reusable workflows, and deploy-output artifacts.

<a id="ir-0012-auth0-tenant-ops-authority-boundary"></a>
### IR-0012 Auth0 tenant-ops authority boundary

Auth0 tenant automation remains bounded to repo-owned template, scripts, and
reusable workflow surfaces.

<a id="ir-0013-ssm-base-url-source-of-truth-for-release-validation"></a>
### IR-0013 Deploy-output source of truth for release validation

Historical SSM-only base-url assumptions are no longer active. Release
validation authority is deploy-output-first, with runtime config parameters
supporting deployment assembly.

<a id="ir-0014-superseded-architecture-archive-boundary"></a>
### IR-0014 Superseded architecture archive boundary

Historical plans, audits, decision frameworks, and superseded ADR/SPEC
material may be retained for traceability but must not remain in the active
router path.

## Release and automation requirements

<a id="release-and-automation-requirements"></a>

- GitHub remains responsible for PR CI, manual release-plan preview, reusable
  validation workflows, and Auth0 tenant operations only.
- AWS CodePipeline + CodeBuild remain the only supported post-merge publish,
  promote, and deploy executor.
- Release metadata remains committed under `release/`.
- Runtime deploy inputs remain account-neutral and tenant-neutral: account ids,
  Route 53 values, certificates, CodeConnections ARNs, CodeArtifact repos, and
  Auth0 tenant coordinates stay configurable inputs, not hardcoded repo truth.
- `NovaReleaseSupportStack` is the default provider of the dev/prod
  CloudFormation execution roles for the release control plane unless explicit
  equivalent role ARNs are supplied.
- When `NovaReleaseSupportStack` owns that default execution-role path, release
  deploy stages must fail closed if the deployed support-stack template drifts
  from the checked-in repo before runtime `aws-cdk deploy`.
- Runtime deploy and validation authority remain bound to `deploy-output.json`
  plus `deploy-output.sha256` rather than free-text base URL inputs.

## Auth0 requirements

- Auth0 tenant-as-code remains driven by the shared template under
  `infra/auth0/tenant/tenant.yaml` plus environment mappings.
- The canonical automation path is:
  - `validate_auth0_contract`
  - `bootstrap_auth0_tenant`
  - `audit_auth0_tenant`
  - `run_auth0_deploy_cli`
- `auth0-python` is the canonical programmatic SDK for tenant bootstrap and
  audit.
- `auth0-deploy-cli` remains the canonical declarative import/export engine.
- GitHub-hosted Auth0 workflows must read credentials from environment-scoped
  secrets (`auth0-dev`, `auth0-pr`, `auth0-qa`), not repo-wide Auth0 secrets.

## Quality requirements

<a id="quality-requirements"></a>

- Active docs must describe implemented state, not target-state aspiration.
- Generated contracts and generated docs must be derived from canonical
  sources and updated in the same change set as source changes.
- Infra, workflow, and docs contract tests must remain authoritative and
  deterministic.
- Personal-account values may appear in live operators’ local env files and AWS
  parameters, but active repo docs/examples should use placeholders unless a
  concrete live example is explicitly labeled as such.

## Temporary exception tracking

- The first production custom-domain cutover may use wildcard browser CORS
  (`allowed_origins=["*"]`) to reduce launch friction.
- That exception is temporary and is tracked by GitHub issue `#111`:
  `Harden prod CORS origins after initial api-nova cutover`.
