"""Workflow productization contracts for reusable workflows and composites."""

# ruff: noqa: I001

from __future__ import annotations

from typing import TypedDict

import yaml

from .helpers import REPO_ROOT, read_repo_file as _read


class _RequiredWorkflowExpectation(TypedDict):
    gated_jobs: dict[str, str]


def test_reusable_workflow_call_apis_exist_and_are_callable() -> None:
    """Reusable workflows must expose explicit workflow_call APIs."""
    for rel_path in [
        ".github/workflows/reusable-release-plan.yml",
        ".github/workflows/reusable-release-apply.yml",
        ".github/workflows/reusable-bootstrap-foundation.yml",
        ".github/workflows/reusable-deploy-runtime.yml",
        ".github/workflows/reusable-deploy-dev.yml",
        ".github/workflows/reusable-promote-prod.yml",
        ".github/workflows/reusable-post-deploy-validate.yml",
        ".github/workflows/reusable-auth0-tenant-deploy.yml",
    ]:
        workflow = yaml.safe_load(_read(rel_path))
        assert isinstance(workflow, dict), (
            f"Expected mapping workflow for: {rel_path}"
        )
        on_contract = workflow.get("on")
        if on_contract is None:
            on_contract = workflow.get(True)
        assert isinstance(on_contract, dict), (
            f"Expected workflow on mapping for: {rel_path}"
        )
        workflow_call = on_contract.get("workflow_call")
        assert isinstance(workflow_call, dict), (
            f"Expected workflow_call mapping for: {rel_path}"
        )


def test_composite_actions_provide_shared_release_primitives() -> None:
    """Shared composite actions must exist for bootstrap and pipeline ops."""
    required_contracts = {
        ".github/actions/setup-python-uv/action.yml": [
            "using: composite",
            "actions/setup-python@v6",
            "astral-sh/setup-uv@v7",
            "version-file: pyproject.toml",
            "enable-cache: true",
            "prune-cache: true",
            "uv sync",
        ],
        ".github/actions/configure-aws-oidc/action.yml": [
            "using: composite",
            "aws-actions/configure-aws-credentials@v6",
            "role-to-assume",
            "aws-region",
        ],
        ".github/actions/configure-release-signing/action.yml": [
            "using: composite",
            "aws secretsmanager get-secret-value",
            "git config commit.gpgsign true",
        ],
        ".github/actions/codepipeline-start/action.yml": [
            "using: composite",
            "codepipeline start-pipeline-execution",
            "Invalid pipeline name",
        ],
        ".github/actions/codepipeline-approve/action.yml": [
            "using: composite",
            "codepipeline get-pipeline-state",
            "codepipeline put-approval-result",
            "Approval token not found",
        ],
        ".github/actions/resolve-size-profile/action.yml": [
            "using: composite",
            "app-type",
            "size-profile",
            "container-port",
            "task-cpu",
            "task-memory",
            "desired-count",
        ],
        ".github/actions/cfn-change-set-lifecycle/action.yml": [
            "using: composite",
            "create-change-set",
            "execute-change-set",
            "no-fail-on-empty-changeset",
            "aws cloudformation describe-events",
            "--change-set-name",
            "OperationEvents",
        ],
        ".github/actions/collect-deploy-evidence/action.yml": [
            "using: composite",
            "describe-stacks",
            "get-pipeline-state",
            "deploy-evidence",
        ],
    }

    for rel_path, required_strings in required_contracts.items():
        text = _read(rel_path)
        for required in required_strings:
            assert required in text, (
                f"Missing composite action contract in {rel_path}: {required!r}"
            )

    cfn_lifecycle_text = _read(
        ".github/actions/cfn-change-set-lifecycle/action.yml"
    )
    assert "--change-set-id" not in cfn_lifecycle_text, (
        "Composite action must use change-set-name validation flow, not "
        f"legacy change-set-id queries:\n{cfn_lifecycle_text}"
    )
    assert '--query "Events[' not in cfn_lifecycle_text, (
        "Composite action must query OperationEvents instead of legacy Events "
        f"output:\n{cfn_lifecycle_text}"
    )


def test_reusable_deploy_runtime_contract_includes_typed_inputs_outputs() -> (
    None
):
    """Reusable deploy-runtime workflow must expose v1 typed contract keys."""
    workflow_text = _read(".github/workflows/reusable-deploy-runtime.yml")
    workflow = yaml.safe_load(workflow_text)
    assert isinstance(workflow, dict)
    on_contract = workflow.get("on")
    if on_contract is None:
        on_contract = workflow.get(True)
    assert isinstance(on_contract, dict)
    workflow_call = on_contract.get("workflow_call")
    assert isinstance(workflow_call, dict)

    inputs = workflow_call.get("inputs", {})
    outputs = workflow_call.get("outputs", {})
    assert isinstance(inputs, dict)
    assert isinstance(outputs, dict)

    for required in [
        "template_file",
        "image_digest",
        "custom_container_port",
        "custom_task_cpu",
        "custom_task_memory",
        "custom_desired_count",
        "app_type",
        "environment",
        "aws_region",
        "parameter_file",
        "size_profile",
        "runtime_cost_mode",
        "enable_worker",
        "approval_environment",
        "stack_name",
    ]:
        assert required in inputs

    for required in [
        "stack_name",
        "change_set_name",
        "pipeline_execution_id",
        "validation_report_path",
        "manifest_sha256",
    ]:
        assert required in outputs

    for required in (
        "resolve-size-profile",
        "cfn-change-set-lifecycle",
        "collect-deploy-evidence",
    ):
        assert required in workflow_text

    assert "image_tag" not in inputs


def test_cfn_contract_validate_workflow_exists_for_cfn_gates() -> None:
    """CI must include CFN syntax/schema and preflight contract validation."""
    text = _read(".github/workflows/cfn-contract-validate.yml")
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    assert workflow.get("name") == "CFN Contract Validate"

    on_contract = workflow.get("on")
    if on_contract is None:
        on_contract = workflow.get(True)
    assert isinstance(on_contract, dict)
    assert "workflow_dispatch" in on_contract
    assert "merge_group" in on_contract
    assert "paths" not in workflow
    pull_request_on = on_contract.get("pull_request")
    if isinstance(pull_request_on, dict):
        assert "paths" not in pull_request_on
        assert "paths-ignore" not in pull_request_on
    push_on = on_contract.get("push")
    if isinstance(push_on, dict):
        assert "paths" not in push_on
        assert "paths-ignore" not in push_on

    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    assert "cfn-and-contracts" in jobs

    classify_job = jobs.get("classify-changes")
    assert isinstance(classify_job, dict)
    classify_steps = classify_job.get("steps")
    assert isinstance(classify_steps, list)
    assert any(
        isinstance(step, dict)
        and "scripts/ci/detect_workflow_scopes.py" in str(step.get("run", ""))
        for step in classify_steps
    )

    cfn_job = jobs.get("cfn-and-contracts")
    assert isinstance(cfn_job, dict)
    cfn_job_text = yaml.safe_dump(cfn_job, sort_keys=False)
    for required in [
        "cfn-lint",
        "infra/nova/*.yml",
        "infra/nova/deploy/*.yml",
        "infra/runtime/**/*.yml",
        "test_absorbed_infra_contracts.py",
        "test_ci_scope_detector.py",
        "test_release_workflow_contracts.py",
        "test_workflow_productization_contracts.py",
        "test_workflow_contract_docs.py",
        "test_docs_authority_contracts.py",
    ]:
        assert required in cfn_job_text


def test_unified_ci_workflow_exists_for_runtime_and_conformance_gates() -> None:
    """Phase 2 must keep runtime and conformance checks in one shell."""
    text = _read(".github/workflows/ci.yml")
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    assert workflow.get("name") == "Nova CI"

    on_contract = workflow.get("on")
    if on_contract is None:
        on_contract = workflow.get(True)
    assert isinstance(on_contract, dict)
    assert "pull_request" in on_contract
    assert "merge_group" in on_contract
    assert "push" in on_contract

    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    for required in [
        "classify-changes",
        "quality-gates",
        "python-compatibility",
        "generated-clients",
        "typescript-core-packages",
        "typescript-sdk-smoke",
        "dash-conformance",
        "shiny-conformance",
        "typescript-conformance",
    ]:
        assert required in jobs
    assert "runtime-security-reliability-gates" not in jobs


def test_required_ci_workflows_use_scope_classifier_gate() -> None:
    """Required workflows must always trigger and gate heavy jobs by scope."""
    required_workflows: dict[str, _RequiredWorkflowExpectation] = {
        ".github/workflows/ci.yml": {
            "gated_jobs": {
                "quality-gates": "run_runtime_ci",
                "python-compatibility": "run_runtime_ci",
                "generated-clients": "run_generated_clients",
                "typescript-core-packages": "run_typescript_conformance",
                "typescript-sdk-smoke": "run_typescript_conformance",
                "dash-conformance": "run_dash_conformance",
                "shiny-conformance": "run_shiny_conformance",
                "typescript-conformance": "run_typescript_conformance",
            },
        },
        ".github/workflows/cfn-contract-validate.yml": {
            "gated_jobs": {"cfn-and-contracts": "run_cfn"},
        },
    }

    for rel_path, expectation in required_workflows.items():
        workflow = yaml.safe_load(_read(rel_path))
        assert isinstance(workflow, dict)
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict)

        classifier = jobs.get("classify-changes")
        assert isinstance(classifier, dict), (
            f"Missing classify-changes job in {rel_path}"
        )
        classifier_steps = classifier.get("steps")
        assert isinstance(classifier_steps, list)
        assert any(
            isinstance(step, dict)
            and "scripts/ci/detect_workflow_scopes.py"
            in str(step.get("run", ""))
            for step in classifier_steps
        ), f"Missing scope detector invocation in {rel_path}"

        classifier_outputs = classifier.get("outputs")
        assert isinstance(classifier_outputs, dict)

        for job_name, classifier_output in expectation["gated_jobs"].items():
            assert classifier_output in classifier_outputs, (
                f"Missing classifier output {classifier_output} in {rel_path}"
            )
            job = jobs.get(job_name)
            assert isinstance(job, dict), (
                f"Missing expected gated job {job_name!r} in {rel_path}"
            )
            job_needs = job.get("needs")
            if isinstance(job_needs, str):
                needs_list = [job_needs]
            elif isinstance(job_needs, list):
                needs_list = job_needs
            else:
                needs_list = []
            assert "classify-changes" in needs_list, (
                "Expected classify-changes job dependency in "
                f"{job_name!r} for {rel_path}"
            )
            condition = str(job.get("if", ""))
            assert "classify-changes" in condition, (
                f"Expected {job_name!r} to depend on classifier in {rel_path}"
            )
            assert classifier_output in condition, (
                f"Expected {job_name!r} to gate on "
                f"{classifier_output} in {rel_path}"
            )


def test_sdk_conformance_shared_r_check_helper_is_used() -> None:
    """SDK conformance lanes must share the warning-fail R helper."""
    workflow_text = _read(".github/workflows/ci.yml")
    script_text = _read("scripts/checks/run_sdk_conformance.sh")
    helper_text = _read("scripts/checks/verify_r_cmd_check.sh")

    assert "scripts/checks/verify_r_cmd_check.sh" in workflow_text
    assert "scripts/checks/verify_r_cmd_check.sh" in script_text
    assert "--no-manual" in helper_text
    assert "R CMD check reported warnings" in helper_text


def test_python_compatibility_job_covers_supported_envs() -> None:
    """Compatibility lane must execute against synced supported envs."""
    workflow = yaml.safe_load(_read(".github/workflows/ci.yml"))
    assert isinstance(workflow, dict)
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    job = jobs.get("python-compatibility")
    assert isinstance(job, dict)
    steps = job.get("steps")
    assert isinstance(steps, list)

    setup_versions = [
        step.get("with", {}).get("python-version")
        for step in steps
        if isinstance(step, dict)
        and step.get("uses") == "./.github/actions/setup-python-uv"
        and isinstance(step.get("with"), dict)
    ]
    build_runs = [
        step.get("run")
        for step in steps
        if isinstance(step, dict)
        and step.get("name", "").startswith("Workspace Build")
        and isinstance(step.get("run"), str)
    ]

    assert "3.11" in setup_versions
    assert "3.12" in setup_versions
    assert any("packages/nova_sdk_py_file" in run for run in build_runs)
    assert any("uv build --python 3.11" in run for run in build_runs)
    assert any("uv build --python 3.12" in run for run in build_runs)


def test_reusable_deploy_dev_checks_out_workflow_source_for_local_actions() -> (
    None
):
    """Reusable deploy-dev must checkout source before local actions."""
    text = _read(".github/workflows/reusable-deploy-dev.yml")

    for required in [
        "WORKFLOW_SOURCE_REPOSITORY",
        "WORKFLOW_SOURCE_SHA",
        "github.workflow_sha",
        "actions/checkout@v6",
        "repository: ${{ env.WORKFLOW_SOURCE_REPOSITORY }}",
        "ref: ${{ env.WORKFLOW_SOURCE_SHA }}",
        "uses: ./.github/actions/configure-aws-oidc",
        "uses: ./.github/actions/codepipeline-start",
    ]:
        assert required in text


def test_standalone_conformance_clients_workflow_is_removed() -> None:
    """Phase 2 must unify PR/runtime and conformance under ci.yml."""
    assert not (
        REPO_ROOT / ".github/workflows/conformance-clients.yml"
    ).exists()


def test_canonical_runtime_deploy_script_enforces_final_posture() -> None:
    """Canonical runtime convergence must live in one operator script."""
    text = _read("scripts/release/deploy-runtime-cloudformation-environment.sh")

    for required in [
        "infra/runtime/kms.yml",
        "infra/runtime/ecr.yml",
        "infra/runtime/ecs/cluster.yml",
        "infra/runtime/file_transfer/s3.yml",
        "infra/runtime/file_transfer/async.yml",
        "infra/runtime/file_transfer/cache.yml",
        "infra/runtime/ecs/service.yml",
        "infra/runtime/file_transfer/worker.yml",
        "infra/runtime/observability/ecs-observability-baseline.yml",
        "infra/nova/deploy/service-base-url-ssm.yml",
        "--no-execute-changeset",
        "--change-set-name",
        "AssignPublicIp=DISABLED",
        "FileTransferAsyncEnabled=true",
        "FileTransferCacheEnabled=true",
        "Runtime file-transfer bucket must not reuse the CI artifact bucket",
        "Unsupported legacy environment variable:",
        "TASK_ROLE_ARN",
        "TASK_EXECUTION_SECRET_ARNS",
        "TASK_EXECUTION_SSM_PARAMETER_ARNS",
        "com.amazonaws.global.cloudfront.origin-facing",
        "describe-managed-prefix-lists",
        '"AlbIngressPrefixListId=${CLOUDFRONT_MANAGED_PREFIX_LIST_ID}"',
        '"LoadBalancerDomainName=${ALB_DNS_NAME}"',
    ]:
        assert required in text

    assert "AllowExecutionRoleSecretsWildcard" not in text
    assert "require_exactly_one_ingress_source" not in text
    assert (
        "ENV_VARS_JSON contains forbidden keys from the runtime contract:"
        in text
    )
    assert (
        "IDEMPOTENCY_ENABLED=true requires FILE_TRANSFER_CACHE_ENABLED=true"
        in text
    )
    assert '[ -n "${!name+x}" ]' in text
    assert "require_env TASK_ROLE_ARN" not in text
    assert '"TaskRole=${TASK_ROLE_ARN}"' not in text
    assert '"TaskExecutionSecretArns=${TASK_EXECUTION_SECRET_ARNS}"' not in text
    assert (
        '"TaskExecutionSsmParameterArns=${TASK_EXECUTION_SSM_PARAMETER_ARNS}"'
        not in text
    )
    assert '"EnvVars=${ENV_VARS_JSON}"' not in text
    assert '"JobsQueueUrl=${JOBS_QUEUE_URL}"' in text
    assert '"JobsTableName=${JOBS_TABLE_NAME}"' in text
    assert '"JobsTableArn=${JOBS_TABLE_ARN}"' in text
    assert '"ActivityTableName=${ACTIVITY_TABLE_NAME}"' in text
    assert '"ActivityTableArn=${ACTIVITY_TABLE_ARN}"' in text
    assert '"CacheRedisUrlSecretArn=${CACHE_URL_SECRET_ARN}"' in text
    assert "LoadBalancerDnsHostname" not in text
    assert '"AlbIngressPrefixListId=${ALB_INGRESS_PREFIX_LIST_ID}"' not in text
    assert '"AlbIngressCidr=${ALB_INGRESS_CIDR}"' not in text
    assert (
        '"AlbIngressSourceSecurityGroupId=${ALB_INGRESS_SOURCE_SG_ID}"'
        not in text
    )


def test_runtime_deploy_script_enforces_visibility_and_execute_mode() -> None:
    """Runtime deploy script must fail fast on invalid queue timeout.

    The script also must remain executable for operators.
    """
    rel_path = "scripts/release/deploy-runtime-cloudformation-environment.sh"
    text = _read(rel_path)

    assert (
        'if ! [[ "$JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then'
        in text
    )
    assert 'JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -lt 1' in text
    assert 'JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -gt 43200' in text
    assert "between 1 and 43200 (12 hours)" in text

    script_path = REPO_ROOT / rel_path
    assert script_path.stat().st_mode & 0o111, (
        f"Expected operator script to be executable: {script_path}"
    )
