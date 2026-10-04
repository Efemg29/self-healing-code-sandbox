"""Tests for the Instructor LLM client mock path."""

from core.config import Settings
from core.llm_client import LLMClient


def _mock_settings(**overrides) -> Settings:
    base = dict(
        openai_api_key=None,
        mock_llm=True,
        allow_local_sandbox=True,
        max_retries=3,
    )
    base.update(overrides)
    return Settings(**base)


def test_mock_generate_add_is_intentionally_buggy():
    client = LLMClient(_mock_settings())
    gen = client.generate_code("Write a function add(a, b) that returns the sum.")
    assert "def add" in gen.implementation_code
    assert "+ 1" in gen.implementation_code
    assert "from solution import add" in gen.test_code


def test_mock_correct_heals_add_bug():
    client = LLMClient(_mock_settings())
    gen = client.generate_code("add two numbers")
    fix = client.correct_code(
        task_description="add two numbers",
        implementation_code=gen.implementation_code,
        test_code=gen.test_code,
        pruned_error="AssertionError: assert 6 == 5",
    )
    assert "a + b + 1" not in fix.fixed_implementation
    assert "return a + b" in fix.fixed_implementation
    assert fix.is_test_flawed is False


def test_mock_factorial_path():
    client = LLMClient(_mock_settings())
    gen = client.generate_code("Write factorial(n)")
    assert "def factorial" in gen.implementation_code
    fix = client.correct_code(
        task_description="Write factorial(n)",
        implementation_code=gen.implementation_code,
        test_code=gen.test_code,
        pruned_error="AssertionError",
    )
    assert "return 1" in fix.fixed_implementation
