"""IAM helpers for least-privilege Nova workflow task roles."""

from __future__ import annotations

from aws_cdk import (
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
)

_EXPORT_STATUS_ACTIONS = [
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
]


def _object_key_pattern(prefix: str) -> str:
    """Return one object-pattern string for an S3 grant prefix."""
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return f"{normalized_prefix}*"


def grant_export_status_permissions(
    function: lambda_.IFunction,
    *,
    export_table: dynamodb.ITable,
) -> None:
    """Grant DynamoDB permissions required for export status writes.

    Args:
        function: Lambda function receiving the inline policy statement.
        export_table: DynamoDB table that stores export status records.

    Returns:
        None.
    """
    function.add_to_role_policy(
        iam.PolicyStatement(
            actions=_EXPORT_STATUS_ACTIONS,
            resources=[export_table.table_arn],
        )
    )


def grant_copy_export_permissions(
    function: lambda_.IFunction,
    *,
    export_table: dynamodb.ITable,
    file_bucket: s3.IBucket,
    upload_prefix: str,
    export_prefix: str,
) -> None:
    """Grant DynamoDB and S3 object permissions required by copy tasks.

    Args:
        function: Lambda function receiving the inline policy statements.
        export_table: DynamoDB table that stores export status records.
        file_bucket: S3 bucket containing upload and export object prefixes.
        upload_prefix: Prefix from which copy tasks read source objects.
        export_prefix: Prefix to which copy tasks write exported objects.

    Returns:
        None.
    """
    grant_export_status_permissions(function, export_table=export_table)
    function.add_to_role_policy(
        iam.PolicyStatement(
            actions=["s3:GetObject*"],
            resources=[
                file_bucket.arn_for_objects(_object_key_pattern(upload_prefix))
            ],
        )
    )
    function.add_to_role_policy(
        iam.PolicyStatement(
            actions=["s3:AbortMultipartUpload", "s3:PutObject*"],
            resources=[
                file_bucket.arn_for_objects(_object_key_pattern(export_prefix))
            ],
        )
    )
