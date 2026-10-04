"""Tests for strict Pydantic schemas."""

from core.models import (
    CodeGenerationResponse,
    CorrectionResponse,
    HealRequest,
    HealResult,
    RunStatus,
    SandboxResult,
)


def test_code_generation_response_fields():
    payload = CodeGenerationResponse(
        thinking_process="plan",
        implementation_code="def f():\n    return 1\n",
        test_code="def test_f():\n    assert True\n",
    )
    assert "def f" in payload.implementation_code


def test_sandbox_result_success_flag():
    ok = SandboxResult(success=True, stdout="ok", stderr="", exit_code=0)
    fail = SandboxResult(success=False, stdout="", stderr="boom", exit_code=1)
    assert ok.success and not fail.success


def test_correction_response_flags():
    fix = CorrectionResponse(
        root_cause="off-by-one",
        is_test_flawed=False,
        fixed_implementation="def add(a, b):\n    return a + b\n",
        fixed_test="def test_add():\n    assert True\n",
    )
    assert fix.is_test_flawed is False


def test_heal_request_min_length():
    req = HealRequest(task_description="add two numbers")
    assert req.task_description.startswith("add")


def test_heal_result_serializes():
    result = HealResult(
        status=RunStatus.SUCCESS,
        task_description="demo",
        attempts=1,
        implementation_code="x = 1",
        test_code="assert True",
        mock_mode=True,
    )
    data = result.model_dump(mode="json")
    assert data["status"] == "success"
    assert data["mock_mode"] is True
