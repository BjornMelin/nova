# Rejected and Deferred Options

## Purpose

These options were seriously considered but were not promoted into the final implementation program because they did not score above 9.0, or because the evidence was not strong enough to justify making them part of the green-field branch plan.

## 1) Edge-only auth as the primary auth layer

### Considered variants

- ALB JWT verification as primary enforcement
- API Gateway HTTP API JWT authorizer as primary enforcement

### Why not final

These are useful **adjuncts**, but not the primary answer for Nova:

- ALB JWT verification is limited (for example, RS256-only and limited claim-check semantics)
- API Gateway JWT authorizers are stronger, but shift the front-door architecture and still do not replace Nova's in-app principal normalization and authorization semantics
- Nova still needs app-level auth for reliable claim normalization, scope/permission interpretation, and consistent SDK-facing errors

### Verdict

Use in-app auth as the source of truth. Edge verification may be added later as defense-in-depth, not as the core design.

## 2) Lambda as the primary compute platform

### Why it scored well but not high enough

Lambda is attractive for spiky APIs and low-ops operations, but Nova is not only an API:

- it also has a long-running worker shape
- it benefits from shared image/runtime semantics between API and worker
- predictable latency and simpler shared code paths favor ECS/Fargate here

### Verdict

Rejected as the primary final platform for this repo.

## 3) App Runner as the primary compute platform

### Why not final

App Runner is attractive for minimal ops, but it is weaker than ECS/Fargate for:

- the worker/service split Nova needs
- the current degree of platform control desired
- richer deployment and observability patterns

### Verdict

Not chosen.

## 4) EKS / Kubernetes

### Why not final

Kubernetes solves problems Nova does not currently have. It adds cluster operational burden without enough payoff for the current workload shape.

### Verdict

Rejected unless future requirements explicitly need Kubernetes primitives.

## 5) DynamoDB TTL as a full replacement for Redis idempotency behavior

### Why not final

DynamoDB TTL deletion is eventual rather than immediate. That can be fine in some systems, but it makes this a weaker direct replacement for short-latency replay/idempotency semantics without a more careful redesign.

### Verdict

Deferred. Keep Redis where it is still materially earning its keep.

## 6) OpenAPI Generator's R client

### Why not final

The upstream R generator is documented as beta and has notable feature gaps, including auth/schema limitations that matter for Nova.

### Verdict

Rejected in favor of a thin `httr2` package.

## 7) Hand-authored static OpenAPI as the source of truth

### Why not final

This would swap one maintenance burden for another. Nova's contract is best expressed in route code with native FastAPI facilities, not in a separately maintained static document.

### Verdict

Rejected.

## 8) Large-scale package renaming (`nova_file_api` -> `nova_api`, etc.)

### Why not final

Renaming every package would create a lot of churn without a commensurate architecture win. The better move is to delete systems and simplify behavior first.

### Verdict

Deferred unless a later maintainability pass proves the renames are worth it.

## 9) Blind adoption of newer aioboto3 S3 copy helpers

### Why not final

aioboto3 has improved its S3 transfer support, but Nova's copy/export semantics need careful validation around metadata, concurrency, and error behavior before changing a core transfer path.

### Verdict

Defer until after the major architecture cuts land and the remaining runtime is simpler.
