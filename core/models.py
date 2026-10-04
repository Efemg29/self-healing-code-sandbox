"""Strict Pydantic schemas for LLM I/O and sandbox results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CodeGenerationResponse(BaseModel):
    thinking_process: str = Field(
        description="Step-by-step reasoning and logic layout (Chain of Thought)"
    )
    implementation_code: str = Field(
        description="Pure Python code only. No markdown formatting or external comments."
    )
    test_code: str = Field(
        description="Comprehensive pytest code covering the implementation."
    )


class SandboxResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int


class CorrectionResponse(BaseModel):
    root_cause: str = Field(description="Concise root cause analysis of the failure")
    is_test_flawed: bool = Field(
        description=(
            "Boolean indicating if the test logic itself is flawed rather than "
            "the implementation"
        )
    )
    fixed_implementation: str = Field(description="The patched pure Python code")
    fixed_test: str = Field(description="The patched pytest code")


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class HealRequest(BaseModel):
    task_description: str = Field(
        min_length=3,
        description="Natural-language description of the coding task to solve.",
    )


class AttemptRecord(BaseModel):
    attempt: int
    success: bool
    pruned_error: str | None = None
    root_cause: str | None = None
    is_test_flawed: bool | None = None


class HealResult(BaseModel):
    status: RunStatus
    task_description: str
    attempts: int
    implementation_code: str
    test_code: str
    thinking_process: str | None = None
    stdout: str = ""
    stderr: str = ""
    final_error: str | None = None
    history: list[AttemptRecord] = Field(default_factory=list)
    mock_mode: bool = False
