# Target Architecture

## Final architecture

```text
Internet clients / Dash apps / TS apps / R Shiny apps
                |
        CloudFront (+ AWS WAF)
                |
               ALB
                |
      +-----------------------+
      | ECS / Fargate cluster |
      +-----------------------+
         |                |
         |                +--> Worker service
         |                     - long-poll SQS
         |                     - direct job/result persistence
         |                     - shared TransferService code
         |
         +--> Public API service
               - FastAPI
               - async JWT verification
               - presigned upload / transfer / jobs APIs
               - OpenAPI source of truth
               - emits metrics / traces / structured logs

Supporting services:
- S3 for uploads / exports / temp objects
- SQS for async job queue
- DynamoDB for jobs + activity rollups
- Redis only where it still earns its keep (idempotency/shared claim store), not as a default metadata datastore
- Secrets Manager / SSM Parameter Store for secrets + runtime config
- CloudWatch + ADOT/OpenTelemetry for logs, metrics, traces
```

## Why this is the final platform

The chosen end-to-end platform scored **9.23/10** in the AWS decision framework. It fits Nova's shape:

- steady HTTP API, not just bursty event traffic
- long-running worker process with shared runtime/service code
- desire for predictable latency and simpler operational boundaries
- desire to keep AWS service count reasonable and rely on managed infrastructure
- need for straightforward Docker/image-based deployment of API and worker from one codebase

## Security model

### Identity and access

- public callers authenticate with **bearer JWT**
- JWT verification happens in-app using the canonical async verifier
- the application is the source of truth for claim normalization and authorization decisions
- ALB JWT verification may be added later only as coarse edge filtering for compatible M2M traffic; it is **not** the primary auth layer

### IAM

- ECS task roles only; no static AWS credentials in code, images, or CI
- least-privilege S3, SQS, DynamoDB, KMS, CloudWatch, and secrets access
- CI deploys via assumed roles / ephemeral credentials only

### Network

- tasks in private subnets
- only CloudFront and ALB are exposed
- Security Groups are the micro-perimeter
- use VPC endpoints where they materially reduce NAT dependence/cost

### Secrets and config

- Secrets Manager for secret values
- SSM Parameter Store for non-secret runtime config
- KMS encryption at rest
- no plaintext secrets in env files committed to the repo

## Reliability plan

- multi-AZ ECS/Fargate services
- separate API and worker services, each independently scalable
- SQS decouples async job execution from API latency
- DynamoDB for durable job/activity state
- retries with backoff and bounded timeouts on AWS SDK and HTTP clients
- ECS blue/green deployments with rollback alarms
- health endpoints:
  - liveness: shallow process health
  - readiness: bounded dependency readiness for traffic-critical services

## Observability plan

### Logs

- structured JSON logs
- correlation/request IDs on all API requests
- worker logs include `job_id`, `scope_id`, and message metadata where safe

### Metrics

- RED metrics for the public API: rate, errors, duration
- queue depth, dequeue lag, worker completion/failure counts
- DynamoDB/SQS/S3 saturation and throttle signals
- deployment alarms on user-facing symptoms, not only infrastructure metrics

### Traces

- OpenTelemetry / ADOT collector sidecar in ECS tasks
- trace API requests, internal service layers, and worker processing spans
- propagate request IDs and trace IDs consistently

## Cost levers

1. ECS task size and autoscaling policy
2. ALB + CloudFront traffic pattern
3. DynamoDB read/write capacity mode and item design
4. SQS long-poll tuning and worker concurrency
5. NAT usage vs VPC endpoints

## Deployment model

- IaC-managed environments only
- separate prod and non-prod accounts
- blue/green rollout for critical API changes
- one runtime image family, with separate API and worker task definitions/commands
- artifact generation (OpenAPI + SDKs) happens in CI and is validated before release

## Runtime/process model

- one ASGI server per container
- scale horizontally with more tasks, not more nested worker processes inside a task
- prefer Python 3.13 image/runtime for the deployed services where feasible
- keep code syntax/runtime compatible with Python 3.11+ for package ecosystem compatibility

## What this architecture intentionally does *not* do

- no standalone auth service
- no edge-only auth as the primary enforcement mechanism
- no EKS unless Kubernetes-specific needs appear
- no API Gateway unless the public edge requirements change enough to justify it
- no internal self-callback HTTP path for worker result updates
- no extra public compatibility shims for legacy auth/session semantics
