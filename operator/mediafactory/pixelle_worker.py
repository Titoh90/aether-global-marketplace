from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from mediafactory.media_request_router import DispatchPlan


IMPERIO_ROOT = Path(__file__).resolve().parents[2]
PIXELLE_SCRIPT = IMPERIO_ROOT / "PIXELLE_VIDEO" / "generate_video.py"
PIXELLE_VENV_PYTHON = IMPERIO_ROOT / "PIXELLE_VIDEO" / "repo" / ".venv" / "bin" / "python"
DEFAULT_OUTPUT_DIR = IMPERIO_ROOT / "REVENUE" / "videos"
DEFAULT_ENV_FILES = (
    IMPERIO_ROOT.parents[0] / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "IMPERIO_NUCLEO.env",
    IMPERIO_ROOT.parents[0] / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "claude_code_proxy.env",
    Path.home() / "IMPERIO_NUCLEO" / ".env",  # canonical source — loaded last, wins on conflicts
)


@dataclass(frozen=True)
class BackendConfig:
    backend: str
    model: str
    base_url: str | None
    api_key: str | None


@dataclass(frozen=True)
class PixelleRunResult:
    status: str
    output_path: str
    metadata_path: str
    backend_used: str
    model_used: str
    optimized_prompt: str
    error: str | None = None


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
BackendResolver = Callable[[str, str], BackendConfig]


def resolve_backend_config(
    backend: str,
    model: str,
    env: Mapping[str, str] | None = None,
    env_files: Iterable[Path] = DEFAULT_ENV_FILES,
) -> BackendConfig:
    merged_env = _load_env_file_values(env_files)
    merged_env.update(dict(os.environ if env is None else env))

    if backend == "openrouter":
        return BackendConfig(
            backend="openrouter",
            model=model,
            base_url=merged_env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=merged_env.get("OPENROUTER_API_KEY"),
        )

    if backend == "nvidia":
        return BackendConfig(
            backend="nvidia",
            model=model,
            base_url=merged_env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            api_key=merged_env.get("NVIDIA_NIM_API_KEY") or merged_env.get("NVIDIA_API_KEY"),
        )

    return BackendConfig(
        backend="ollama",
        model=model,
        base_url=None,
        api_key=None,
    )


def build_pixelle_command(
    plan: DispatchPlan,
    backend_config: BackendConfig,
    output_dir: Path,
    timestamp: str,
    env: Mapping[str, str] | None = None,
    env_files: Iterable[Path] = DEFAULT_ENV_FILES,
) -> list[str]:
    # Resolve env (for Pexels key + watermark)
    merged_env = _load_env_file_values(env_files)
    merged_env.update(dict(os.environ if env is None else env))

    command = [
        str(_resolve_python()),
        str(PIXELLE_SCRIPT),
        plan.request.topic,
        "--output",
        str(output_dir),
        "--model",
        backend_config.model,
        "--script-brief",
        plan.optimized_prompt,
        "--timestamp",
        timestamp,
    ]

    if backend_config.base_url:
        command.extend(["--llm-base-url", backend_config.base_url])
    if backend_config.api_key:
        command.extend(["--llm-api-key", backend_config.api_key])

    # Pexels stock video (optional — pass key if available)
    pexels_key = merged_env.get("PEXELS_API_KEY", "").strip()
    if pexels_key:
        command.extend(["--pexels-key", pexels_key])

    # Watermark (always on unless explicitly disabled)
    watermark_text = merged_env.get("PIXELLE_WATERMARK", "@alexanderaether • link en bio")
    command.extend(["--watermark-text", watermark_text])

    return command


def run_pixelle_worker(
    plan: DispatchPlan,
    output_dir: Path | None = None,
    timestamp: str | None = None,
    backend_resolver: BackendResolver | None = None,
    command_runner: CommandRunner | None = None,
) -> PixelleRunResult:
    effective_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    effective_timestamp = timestamp or time.strftime("%Y%m%d_%H%M%S")
    resolver = backend_resolver or (
        lambda backend, model: resolve_backend_config(backend=backend, model=model)
    )
    runner = command_runner or _run_command

    backend_config = resolver(
        plan.model_selection.backend,
        plan.model_selection.model,
    )
    command = build_pixelle_command(
        plan=plan,
        backend_config=backend_config,
        output_dir=effective_output_dir,
        timestamp=effective_timestamp,
        env_files=DEFAULT_ENV_FILES,
    )
    result = runner(command)
    output_path, metadata_path = _build_expected_outputs(
        topic=plan.request.topic,
        output_dir=effective_output_dir,
        timestamp=effective_timestamp,
    )

    status = "success" if result.returncode == 0 else "failed"
    return PixelleRunResult(
        status=status,
        output_path=str(output_path),
        metadata_path=str(metadata_path),
        backend_used=backend_config.backend,
        model_used=backend_config.model,
        optimized_prompt=plan.optimized_prompt,
        error=None if result.returncode == 0 else _excerpt_error(result.stderr),
    )


def _resolve_python() -> Path:
    if PIXELLE_VENV_PYTHON.exists():
        return PIXELLE_VENV_PYTHON
    return Path(os.environ.get("PYTHON", "python3"))


def _build_expected_outputs(topic: str, output_dir: Path, timestamp: str) -> tuple[Path, Path]:
    stem = f"pixelle_{_slugify_topic(topic)}_{timestamp}"
    return output_dir / f"{stem}.mp4", output_dir / f"{stem}.json"


def _slugify_topic(topic: str) -> str:
    compact = re.sub(r"[^a-zA-Z0-9]+", "_", topic.lower()).strip("_")
    return compact[:30].strip("_")


def _load_env_file_values(env_files: Iterable[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    for env_file in env_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _excerpt_error(stderr: str) -> str | None:
    cleaned = (stderr or "").strip()
    if not cleaned:
        return None
    return cleaned[-500:]
