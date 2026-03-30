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
- `../architecture/spec/superseded/SPEC-0000-http-api-contract.md`
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

## Best dependency/platform leverage moves in this program

### `oidc-jwt-verifier`

Use the async verifier and FastAPI/Starlette integration helpers instead of a dedicated auth service.

### FastAPI native OpenAPI/security/features

Use `Security(…)`, `response_model=…`, and `responses={…}` instead of hand-editing OpenAPI.

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
