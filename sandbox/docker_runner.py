"""Isolated Docker (or local fallback) runner for pytest execution."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from core.config import Settings, get_settings
from core.models import SandboxResult

logger = logging.getLogger(__name__)


class DockerRunner:
    """Execute pytest for generated code under hard security constraints.

    Mandatory Docker constraints (when Docker is available):
    - network_mode="none"
    - read_only=True (only /app is writable via bind mount)
    - mem_limit="256m"
    - nano_cpus=500000000 (0.5 CPU)
    - pids_limit=50
    - user="nobody"
    - timeout with SIGKILL
    - finally-block force stop/remove to prevent zombie containers

    Note: containers are started with ``detach=True`` so we can ``wait(timeout=...)``
    and issue SIGKILL on overrun. ``remove=True`` is applied in the finally path.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._docker_client = None
        self._docker_available = False
        self._init_docker()

    def _init_docker(self) -> None:
        try:
            import docker

            client = docker.from_env()
            client.ping()
            # GitHub Actions (and many CI hosts) expose a Docker daemon but do not
            # ship our custom sandbox image. Prefer local pytest fallback in that case
            # so mock-mode demos and CI stay green without a prior image build.
            if not self._image_available(client):
                if self.settings.allow_local_sandbox:
                    self._docker_client = None
                    self._docker_available = False
                    logger.warning(
                        "Sandbox image %s not found; using local sandbox fallback.",
                        self.settings.sandbox_image,
                    )
                    return
                logger.warning(
                    "Sandbox image %s not found and local fallback disabled.",
                    self.settings.sandbox_image,
                )
            self._docker_client = client
            self._docker_available = True
            logger.info("Docker daemon reachable; using container sandbox.")
        except Exception as exc:  # noqa: BLE001 - any docker failure falls back
            self._docker_client = None
            self._docker_available = False
            logger.warning(
                "Docker unavailable (%s). Local sandbox fallback=%s",
                exc,
                self.settings.allow_local_sandbox,
            )

    def _image_available(self, client) -> bool:
        try:
            client.images.get(self.settings.sandbox_image)
            return True
        except Exception:  # noqa: BLE001 - missing image or API flake
            return False

    @staticmethod
    def _is_docker_infra_failure(result: SandboxResult) -> bool:
        """True when Docker never executed the suite (image/daemon/setup error)."""
        blob = f"{result.stderr}\n{result.stdout}".lower()
        markers = (
            "no such image",
            "unable to find image",
            "pull access denied",
            "repository does not exist",
            "error response from daemon",
            "cannot connect to the docker",
            "is the docker daemon running",
        )
        return any(marker in blob for marker in markers)

    def run(self, workdir: Path) -> SandboxResult:
        """Run pytest against ``solution.py`` / ``test_solution.py`` in ``workdir``."""
        workdir = Path(workdir).resolve()
        if not (workdir / "solution.py").exists():
            return SandboxResult(
                success=False,
                stdout="",
                stderr="solution.py missing in workdir",
                exit_code=2,
            )
        if not (workdir / "test_solution.py").exists():
            return SandboxResult(
                success=False,
                stdout="",
                stderr="test_solution.py missing in workdir",
                exit_code=2,
            )

        if self._docker_available:
            result = self._run_docker(workdir)
            if (
                not result.success
                and self.settings.allow_local_sandbox
                and self._is_docker_infra_failure(result)
            ):
                logger.warning(
                    "Docker sandbox infra failure (%s); falling back to local pytest.",
                    (result.stderr or result.stdout)[:200],
                )
                return self._run_local(workdir)
            return result
        if self.settings.allow_local_sandbox:
            return self._run_local(workdir)
        return SandboxResult(
            success=False,
            stdout="",
            stderr=(
                "Docker is required but unavailable. "
                "Set ALLOW_LOCAL_SANDBOX=true for host pytest fallback."
            ),
            exit_code=127,
        )

    def _run_docker(self, workdir: Path) -> SandboxResult:
        assert self._docker_client is not None
        container = None
        try:
            container = self._docker_client.containers.run(
                image=self.settings.sandbox_image,
                command=["pytest", "-q", "--tb=short", "test_solution.py"],
                volumes={str(workdir): {"bind": "/app", "mode": "rw"}},
                working_dir="/app",
                network_mode="none",
                read_only=True,
                tmpfs={"/tmp": "size=16m,mode=1777"},
                mem_limit=self.settings.sandbox_mem_limit,
                nano_cpus=self.settings.sandbox_nano_cpus,
                pids_limit=self.settings.sandbox_pids_limit,
                user="nobody",
                detach=True,
                remove=False,
                stdout=True,
                stderr=True,
            )
            try:
                wait_result = container.wait(
                    timeout=self.settings.sandbox_timeout_seconds
                )
            except Exception as wait_exc:  # noqa: BLE001 - timeout or API flake
                logger.warning("Sandbox wait failed/timed out: %s", wait_exc)
                try:
                    container.kill(signal="SIGKILL")
                except Exception:  # noqa: BLE001
                    pass
                logs = self._safe_logs(container)
                return SandboxResult(
                    success=False,
                    stdout=logs["stdout"],
                    stderr=(
                        f"Sandbox timed out after "
                        f"{self.settings.sandbox_timeout_seconds}s (SIGKILL)\n"
                        f"{logs['stderr']}"
                    ),
                    exit_code=124,
                )

            exit_code = int(wait_result.get("StatusCode", 1))
            logs = self._safe_logs(container)
            return SandboxResult(
                success=exit_code == 0,
                stdout=logs["stdout"],
                stderr=logs["stderr"],
                exit_code=exit_code,
            )
        except Exception as exc:  # noqa: BLE001
            logs = self._safe_logs(container) if container is not None else {
                "stdout": "",
                "stderr": "",
            }
            return SandboxResult(
                success=False,
                stdout=logs["stdout"],
                stderr=logs["stderr"] or str(exc),
                exit_code=1,
            )
        finally:
            if container is not None:
                try:
                    container.kill(signal="SIGKILL")
                except Exception:  # noqa: BLE001
                    pass
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001
                    pass

    @staticmethod
    def _safe_logs(container) -> dict[str, str]:
        if container is None:
            return {"stdout": "", "stderr": ""}
        try:
            stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )
            return {"stdout": stdout, "stderr": stderr}
        except Exception:  # noqa: BLE001
            return {"stdout": "", "stderr": ""}

    def _run_local(self, workdir: Path) -> SandboxResult:
        """Host pytest fallback when Docker is unavailable (dev / CI without daemon)."""
        pytest_bin = shutil.which("pytest")
        cmd = (
            [pytest_bin, "-q", "--tb=short", "test_solution.py"]
            if pytest_bin
            else [sys.executable, "-m", "pytest", "-q", "--tb=short", "test_solution.py"]
        )
        timeout = self.settings.sandbox_timeout_seconds
        started = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            elapsed = time.monotonic() - started
            logger.info(
                "Local sandbox finished exit=%s in %.2fs",
                completed.returncode,
                elapsed,
            )
            return SandboxResult(
                success=completed.returncode == 0,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                exit_code=completed.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, (bytes, bytearray)):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, (bytes, bytearray)):
                stderr = stderr.decode("utf-8", errors="replace")
            return SandboxResult(
                success=False,
                stdout=stdout,
                stderr=(
                    f"Sandbox timed out after {timeout}s (SIGKILL equivalent)\n{stderr}"
                ),
                exit_code=124,
            )
