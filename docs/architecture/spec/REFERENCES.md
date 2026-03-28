# External references for the current docs + wave-2 program

These are the primary official or upstream references used to shape the current
docs pack and the approved target-state program.

## FastAPI and Starlette

- FastAPI lifespan events:
  <https://fastapi.tiangolo.com/advanced/events/>
- FastAPI security overview:
  <https://fastapi.tiangolo.com/tutorial/security/>
- FastAPI bearer/JWT tutorial examples:
  <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>
- Starlette middleware docs and `BaseHTTPMiddleware` limitations:
  <https://www.starlette.io/middleware/>

## JWT verification

- `oidc-jwt-verifier` docs home:
  <https://oidc-jwt-verifier.bjornmelin.io/>
- `oidc-jwt-verifier` API reference:
  <https://oidc-jwt-verifier.bjornmelin.io/reference/>
- `oidc-jwt-verifier` GitHub repository:
  <https://github.com/BjornMelin/oidc-jwt-verifier>

## AWS platform

- Choose between API Gateway HTTP APIs and REST APIs:
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html>
- API Gateway HTTP APIs overview:
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html>
- Step Functions workflow types:
  <https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html>
- Step Functions overview / Standard workflow duration and exactly-once semantics:
  <https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html>
- Step Functions best practices:
  <https://docs.aws.amazon.com/step-functions/latest/dg/sfn-best-practices.html>
- DynamoDB TTL:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
- Working with expired DynamoDB TTL items:
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ttl-expired-items.html>
- Lambda runtimes:
  <https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html>
- Python Lambda container images:
  <https://docs.aws.amazon.com/lambda/latest/dg/python-image.html>
- Lambda response streaming:
  <https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html>
- AWS Lambda Web Adapter:
  <https://github.com/awslabs/aws-lambda-web-adapter>
- AWS Lambda Web Adapter FastAPI example:
  <https://github.com/awslabs/aws-lambda-web-adapter/blob/main/examples/fastapi/README.md>

## TypeScript SDK generation

- openapi-ts roadmap discussion noting `openapi-fetch` maintenance mode:
  <https://github.com/openapi-ts/openapi-typescript/discussions/2559>
- Hey API / `@hey-api/openapi-ts` get started:
  <https://heyapi.dev/openapi-ts/get-started>
- Hey API clients overview:
  <https://heyapi.dev/openapi-ts/clients>
- Hey API fetch client:
  <https://heyapi.dev/openapi-ts/clients/fetch>
- Hey API output:
  <https://heyapi.dev/openapi-ts/output>
- Hey API migration notes:
  <https://heyapi.dev/openapi-ts/migrating>

## Python SDK generation

- `openapi-python-client` PyPI:
  <https://pypi.org/project/openapi-python-client/>
- `openapi-python-client` GitHub repository:
  <https://github.com/openapi-generators/openapi-python-client>
- `openapi-python-client` changelog:
  <https://github.com/openapi-generators/openapi-python-client/blob/main/CHANGELOG.md>

## R client strategy

- `httr2` home:
  <https://httr2.r-lib.org/>
- `httr2` package index:
  <https://httr2.r-lib.org/reference/index.html>
- `httr2` wrapping APIs article:
  <https://httr2.r-lib.org/articles/wrapping-apis.html>
- `httr2` changelog:
  <https://httr2.r-lib.org/news/index.html>
- `httr` status page (superseded in favor of `httr2`):
  <https://httr.r-lib.org/>
- OpenAPI Generator R generator docs:
  <https://openapi-generator.tech/docs/generators/r/>
