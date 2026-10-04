"""Reflection loop: generate → sandbox → prune → correct → retry."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from core.config import Settings, get_settings
from core.llm_client import LLMClient
from core.models import AttemptRecord, HealResult, RunStatus
from sandbox.docker_runner import DockerRunner
from sandbox.error_pruner import prune_error_log

logger = logging.getLogger(__name__)


class SelfHealingStateMachine:
    """Orchestrates the generate / test / reflect retry loop."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: LLMClient | None = None,
        docker_runner: DockerRunner | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm_client or LLMClient(self.settings)
        self.runner = docker_runner or DockerRunner(self.settings)

    def run(self, task_description: str) -> HealResult:
        """Execute the full self-healing pipeline for ``task_description``."""
        generation = self.llm.generate_code(task_description)
        implementation = generation.implementation_code
        test_code = generation.test_code
        thinking = generation.thinking_process

        history: list[AttemptRecord] = []
        last_stdout = ""
        last_stderr = ""
        last_pruned: str | None = None

        max_attempts = self.settings.max_retries
        for attempt in range(1, max_attempts + 1):
            logger.info("Attempt %s/%s for task=%r", attempt, max_attempts, task_description)

            with tempfile.TemporaryDirectory(prefix="selfheal_") as tmp:
                workdir = Path(tmp)
                (workdir / "solution.py").write_text(implementation, encoding="utf-8")
                (workdir / "test_solution.py").write_text(test_code, encoding="utf-8")
                # Empty __init__ not required; pytest imports solution as a module file.
                result = self.runner.run(workdir)

            last_stdout = result.stdout
            last_stderr = result.stderr

            if result.success:
                history.append(
                    AttemptRecord(
                        attempt=attempt,
                        success=True,
                        pruned_error=None,
                        root_cause=None,
                        is_test_flawed=None,
                    )
                )
                return HealResult(
                    status=RunStatus.SUCCESS,
                    task_description=task_description,
                    attempts=attempt,
                    implementation_code=implementation,
                    test_code=test_code,
                    thinking_process=thinking,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    final_error=None,
                    history=history,
                    mock_mode=self.llm.mock_mode,
                )

            pruned = prune_error_log(result.stderr, result.stdout)
            last_pruned = pruned
            logger.info("Attempt %s failed; reflecting on pruned error.", attempt)

            if attempt >= max_attempts:
                history.append(
                    AttemptRecord(
                        attempt=attempt,
                        success=False,
                        pruned_error=pruned,
                        root_cause=None,
                        is_test_flawed=None,
                    )
                )
                break

            correction = self.llm.correct_code(
                task_description=task_description,
                implementation_code=implementation,
                test_code=test_code,
                pruned_error=pruned,
            )
            history.append(
                AttemptRecord(
                    attempt=attempt,
                    success=False,
                    pruned_error=pruned,
                    root_cause=correction.root_cause,
                    is_test_flawed=correction.is_test_flawed,
                )
            )
            implementation = correction.fixed_implementation
            test_code = correction.fixed_test

        return HealResult(
            status=RunStatus.FAILURE,
            task_description=task_description,
            attempts=max_attempts,
            implementation_code=implementation,
            test_code=test_code,
            thinking_process=thinking,
            stdout=last_stdout,
            stderr=last_stderr,
            final_error=last_pruned or last_stderr or "Max retries exceeded",
            history=history,
            mock_mode=self.llm.mock_mode,
        )
