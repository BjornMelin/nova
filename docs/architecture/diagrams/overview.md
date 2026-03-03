# Overview: Deployable FastAPI service

Service-level view, including direct data plane to S3 and control plane to API.

```mermaid

flowchart LR
  U[Browser client] --> API[FastAPI: /v1/transfers + /v1/jobs + /v1 capability routes]
  API -->|boto3 presign & MPU ops| S3[(S3 bucket)]
  U -->|PUT / UploadPart| S3
  U -->|Complete via API| API
  U -->|GET (presigned)| S3
  API --> CW[(CloudWatch Logs)]

```
