# Dependency leverage audit

> **Implementation state:** Active target-state audit input for the implementation program.

## Authority / references

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `../architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `../architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `../architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `../architecture/requirements.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`

## Principle

Delete repo code whenever an upstream dependency or native platform capability can replace it cleanly without increasing hidden complexity.

## Current applied posture

### Security refreshes applied in the current lock

- Refresh vulnerable transitive packages in `uv.lock` with targeted `uv lock --upgrade-package …` updates instead of a broad resolver sweep.
- Current targeted refresh set: `aiohttp`, `cryptography`, `pygments`, `pyjwt`, `requests`.
- Do not replace this with `uv lock --upgrade` unless the branch explicitly revalidates the broader transitive moves that follow from a full-resolution update.

### Explicit holds

- Keep `typescript` pinned to `5.9.3`.
- Keep the async AWS stack pinned as one unit: `aioboto3`, `aiobotocore`, `boto3`, `botocore`, `types-aiobotocore-s3`.
- Keep the local `@hey-api/openapi-ts` compatibility patch until upstream output no longer emits the `getParseAs` and `RequestOptions<never, …>` cases Nova currently repairs.
- Keep the retained Python SDK typed `additionalProperties` and parser repairs until stock generator output matches the committed SDK without local correction.

### Current native-leverage deletions

- Use shared Pydantic-backed optional env-string normalization instead of repeated local blank-string handling in runtime settings.
- Enable `openapi-python-client` `docstrings_on_attributes` and delete the local Python SDK blank-docstring repair pass.
- Rely on `httr2::req_headers()` plus Nova's named-list normalization and delete the redundant R null-header pruning helper.

## Best dependency/platform leverage moves in this program

### `oidc-jwt-verifier`

Use the async verifier plus the verifier-owned JWKS lifecycle/readiness APIs
instead of a dedicated auth service or Nova-owned readiness wrappers.

### FastAPI native OpenAPI/security/features

Use `Security(…)`, `response_model=…`, `responses={…}`,
`strict_content_type=True`, `lifespan`, instance-level OpenAPI overrides, and
native streaming responses instead of hand-editing OpenAPI or reimplementing
request parsing/runtime wrappers.

### Regional REST API throttling + AWS WAF

Use managed API Gateway throttling and Regional WAF controls instead of bespoke abuse-prevention logic in the app.

### Step Functions Standard

Use durable orchestration instead of a custom worker callback lifecycle.

### DynamoDB

Use DynamoDB for workflow state and idempotency records instead of Redis-backed correctness paths.

### `@hey-api/openapi-ts`

Use a maintained TS SDK generator instead of a bespoke runtime package.

### `openapi-python-client`

Keep it, but stop over-patching the output.

### `httr2`

Use language-native, thin R HTTP wrappers instead of fragile codegen.

### Mangum

Use a native ASGI-to-Lambda adapter to keep FastAPI and OpenAPI while deleting the in-function web-server and Web Adapter layer.
