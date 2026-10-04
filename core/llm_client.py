"""OpenAI client wrapped with Instructor for strict structured outputs."""

from __future__ import annotations

import logging
import re

import instructor
from openai import OpenAI

from core.config import Settings, get_settings
from core.models import CodeGenerationResponse, CorrectionResponse
from core.prompts import (
    CODE_GENERATION_SYSTEM_PROMPT,
    CODE_GENERATION_USER_TEMPLATE,
    CORRECTION_SYSTEM_PROMPT,
    CORRECTION_USER_TEMPLATE,
    FEW_SHOT_IMPLEMENTATION,
    FEW_SHOT_TESTS,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around Instructor + OpenAI with an offline mock fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None
        if not self.settings.mock_llm:
            if not self.settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required unless MOCK_LLM=true is set."
                )
            raw = OpenAI(api_key=self.settings.openai_api_key)
            self._client = instructor.from_openai(raw)

    @property
    def mock_mode(self) -> bool:
        return self.settings.mock_llm

    def generate_code(self, task_description: str) -> CodeGenerationResponse:
        if self.settings.mock_llm:
            return self._mock_generate(task_description)

        assert self._client is not None
        return self._client.chat.completions.create(
            model=self.settings.openai_model,
            response_model=CodeGenerationResponse,
            max_retries=self.settings.instructor_max_retries,
            messages=[
                {"role": "system", "content": CODE_GENERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": CODE_GENERATION_USER_TEMPLATE.format(
                        task_description=task_description
                    ),
                },
            ],
        )

    def correct_code(
        self,
        task_description: str,
        implementation_code: str,
        test_code: str,
        pruned_error: str,
    ) -> CorrectionResponse:
        if self.settings.mock_llm:
            return self._mock_correct(
                task_description=task_description,
                implementation_code=implementation_code,
                test_code=test_code,
                pruned_error=pruned_error,
            )

        assert self._client is not None
        return self._client.chat.completions.create(
            model=self.settings.openai_model,
            response_model=CorrectionResponse,
            max_retries=self.settings.instructor_max_retries,
            messages=[
                {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": CORRECTION_USER_TEMPLATE.format(
                        task_description=task_description,
                        implementation_code=implementation_code,
                        test_code=test_code,
                        pruned_error=pruned_error,
                    ),
                },
            ],
        )

    def _mock_generate(self, task_description: str) -> CodeGenerationResponse:
        """Deterministic offline generator for demos without an API key."""
        logger.info("MOCK_LLM: generating code for task=%r", task_description)
        lowered = task_description.lower()

        if "factorial" in lowered:
            return CodeGenerationResponse(
                thinking_process=(
                    "Need a recursive or iterative factorial. Start with a buggy "
                    "base case so the reflection loop can demonstrate self-healing."
                ),
                implementation_code=(
                    "def factorial(n):\n"
                    "    if n < 0:\n"
                    "        raise ValueError('n must be non-negative')\n"
                    "    if n == 0:\n"
                    "        return 0  # intentional bug for mock reflection\n"
                    "    result = 1\n"
                    "    for i in range(1, n + 1):\n"
                    "        result *= i\n"
                    "    return result\n"
                ),
                test_code=(
                    "from solution import factorial\n"
                    "import pytest\n\n"
                    "def test_factorial_zero():\n"
                    "    assert factorial(0) == 1\n\n"
                    "def test_factorial_five():\n"
                    "    assert factorial(5) == 120\n\n"
                    "def test_factorial_negative():\n"
                    "    with pytest.raises(ValueError):\n"
                    "        factorial(-1)\n"
                ),
            )

        if re.search(r"\bpalindrome\b", lowered):
            return CodeGenerationResponse(
                thinking_process="Normalize case and compare the string to its reverse.",
                implementation_code=(
                    "def is_palindrome(text):\n"
                    "    cleaned = ''.join(ch.lower() for ch in text if ch.isalnum())\n"
                    "    return cleaned == cleaned[::-1]\n"
                ),
                test_code=(
                    "from solution import is_palindrome\n\n"
                    "def test_simple_palindrome():\n"
                    "    assert is_palindrome('racecar') is True\n\n"
                    "def test_non_palindrome():\n"
                    "    assert is_palindrome('cursor') is False\n\n"
                    "def test_phrase_palindrome():\n"
                    "    assert is_palindrome('A man a plan a canal Panama') is True\n"
                ),
            )

        # Default: intentionally buggy add() so one reflection cycle can heal it.
        return CodeGenerationResponse(
            thinking_process=(
                "Implement a basic adder. Seed a deliberate off-by-one bug so the "
                "sandbox fails once and the correction path can patch it."
            ),
            implementation_code=(
                "def add(a, b):\n"
                "    \"\"\"Return the sum of a and b.\"\"\"\n"
                "    return a + b + 1  # intentional bug for mock reflection\n"
            ),
            test_code=FEW_SHOT_TESTS,
        )

    def _mock_correct(
        self,
        task_description: str,
        implementation_code: str,
        test_code: str,
        pruned_error: str,
    ) -> CorrectionResponse:
        logger.info("MOCK_LLM: correcting failure for task=%r", task_description)
        lowered = task_description.lower()

        if "factorial" in lowered or "return 0  # intentional bug" in implementation_code:
            return CorrectionResponse(
                root_cause="factorial(0) incorrectly returned 0 instead of 1.",
                is_test_flawed=False,
                fixed_implementation=(
                    "def factorial(n):\n"
                    "    if n < 0:\n"
                    "        raise ValueError('n must be non-negative')\n"
                    "    if n == 0:\n"
                    "        return 1\n"
                    "    result = 1\n"
                    "    for i in range(1, n + 1):\n"
                    "        result *= i\n"
                    "    return result\n"
                ),
                fixed_test=test_code,
            )

        if "intentional bug" in implementation_code or "add(a, b)" in implementation_code:
            return CorrectionResponse(
                root_cause="add() returned a + b + 1 instead of a + b.",
                is_test_flawed=False,
                fixed_implementation=FEW_SHOT_IMPLEMENTATION,
                fixed_test=test_code or FEW_SHOT_TESTS,
            )

        return CorrectionResponse(
            root_cause=f"Sandbox failure: {pruned_error[:200]}",
            is_test_flawed=False,
            fixed_implementation=implementation_code,
            fixed_test=test_code,
        )
