# Overview: Deployable FastAPI service

Service-level view, including direct data plane to S3 and control plane to API.

```mermaid

flowchart LR
  U[Browser client] --> API[FastAPI: /v1/transfers + /v1/exports + /v1/capabilities]
  API -->|aioboto3 presign & MPU ops| S3[(S3 bucket)]
  U -->|PUT / UploadPart| S3
  U -->|Complete via API| API
  U -->|GET (presigned)| S3
  API --> CW[(CloudWatch Logs)]

```
