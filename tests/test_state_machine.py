"""End-to-end tests for the reflection state machine (mock LLM + local sandbox)."""

from core.config import Settings
from core.llm_client import LLMClient
from core.models import RunStatus
from core.state_machine import SelfHealingStateMachine
from sandbox.docker_runner import DockerRunner


def _machine(max_retries: int = 3) -> SelfHealingStateMachine:
    settings = Settings(
        openai_api_key=None,
        mock_llm=True,
        allow_local_sandbox=True,
        max_retries=max_retries,
        sandbox_timeout_seconds=5,
    )
    runner = DockerRunner(settings)
    runner._docker_available = False
    return SelfHealingStateMachine(
        settings=settings,
        llm_client=LLMClient(settings),
        docker_runner=runner,
    )


def test_heal_add_succeeds_after_reflection():
    result = _machine().run(
        "Write a function add(a, b) that returns the sum of two numbers."
    )
    assert result.status == RunStatus.SUCCESS
    assert result.attempts == 2
    assert result.mock_mode is True
    assert "return a + b" in result.implementation_code
    assert "+ 1" not in result.implementation_code
    assert len(result.history) == 2
    assert result.history[0].success is False
    assert result.history[1].success is True


def test_heal_factorial_succeeds_after_reflection():
    result = _machine().run(
        "Write a function factorial(n) that returns n! for non-negative integers."
    )
    assert result.status == RunStatus.SUCCESS
    assert result.attempts >= 2
    assert "def factorial" in result.implementation_code


def test_heal_palindrome_passes_first_try():
    result = _machine().run(
        "Write is_palindrome(text) that ignores case and non-alphanumerics."
    )
    assert result.status == RunStatus.SUCCESS
    assert result.attempts == 1
