# nova-runtime-support

Internal shared cross-cutting runtime helpers for Nova service packages.

This package is intentionally limited to:

- request context and canonical error transport helpers
- auth claim normalization and JWT verifier construction
- shared structlog and metrics helpers
- shared transfer config constants and policy document models

It does not own export/session/quota/workflow domain logic.
