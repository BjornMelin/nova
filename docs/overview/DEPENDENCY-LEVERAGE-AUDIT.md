# Dependency leverage audit

> **Implementation state:** Active target-state audit input for the implementation program.

## Principle

Delete repo code whenever an upstream dependency or native platform capability can replace it cleanly without increasing hidden complexity.

## Best dependency/platform leverage moves in this program

### `oidc-jwt-verifier`

Use the async verifier and FastAPI/Starlette integration helpers instead of a dedicated auth service.

### FastAPI native OpenAPI/security/features

Use `Security(...)`, `response_model=...`, and `responses={...}` instead of hand-editing OpenAPI.

### API Gateway HTTP API JWT authorizers

Use route-level JWT validation at the edge for coarse gatekeeping where it reduces noise before the app.

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

### AWS Lambda Web Adapter

Use it to keep FastAPI while making Lambda the canonical runtime.
