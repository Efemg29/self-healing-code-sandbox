"""Tests for local sandbox runner behavior."""

from pathlib import Path

from core.config import Settings
from core.models import SandboxResult
from sandbox.docker_runner import DockerRunner


def _settings(**overrides) -> Settings:
    base = dict(
        mock_llm=True,
        allow_local_sandbox=True,
        sandbox_timeout_seconds=5,
        openai_api_key=None,
    )
    base.update(overrides)
    return Settings(**base)


def test_local_runner_passes_correct_code(tmp_path: Path):
    (tmp_path / "solution.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (tmp_path / "test_solution.py").write_text(
        "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    runner = DockerRunner(_settings())
    # Force local path even if docker somehow appears.
    runner._docker_available = False
    result = runner.run(tmp_path)
    assert isinstance(result, SandboxResult)
    assert result.success is True
    assert result.exit_code == 0


def test_local_runner_fails_buggy_code(tmp_path: Path):
    (tmp_path / "solution.py").write_text(
        "def add(a, b):\n    return a + b + 1\n", encoding="utf-8"
    )
    (tmp_path / "test_solution.py").write_text(
        "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    runner = DockerRunner(_settings())
    runner._docker_available = False
    result = runner.run(tmp_path)
    assert result.success is False
    assert result.exit_code != 0


def test_missing_solution_file(tmp_path: Path):
    (tmp_path / "test_solution.py").write_text("def test_x():\n    assert True\n")
    runner = DockerRunner(_settings())
    runner._docker_available = False
    result = runner.run(tmp_path)
    assert result.success is False
    assert "solution.py missing" in result.stderr


def test_docker_required_without_fallback(tmp_path: Path):
    (tmp_path / "solution.py").write_text("x = 1\n")
    (tmp_path / "test_solution.py").write_text("def test_x():\n    assert True\n")
    runner = DockerRunner(_settings(allow_local_sandbox=False))
    runner._docker_available = False
    result = runner.run(tmp_path)
    assert result.exit_code == 127
    assert "Docker is required" in result.stderr
