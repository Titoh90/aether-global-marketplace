from __future__ import annotations

import subprocess
from pathlib import Path

from mediafactory.media_request_router import plan_media_request
from mediafactory.pixelle_worker import (
    BackendConfig,
    PixelleRunResult,
    build_pixelle_command,
    resolve_backend_config,
    run_pixelle_worker,
)


def test_resolve_backend_config_reads_openrouter_key_from_env_file(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "imperio.env"
    env_file.write_text("OPENROUTER_API_KEY=test-openrouter-key\n", encoding="utf-8")

    result = resolve_backend_config(
        backend="openrouter",
        model="openrouter/free",
        env={},
        env_files=(env_file,),
    )

    assert result == BackendConfig(
        backend="openrouter",
        model="openrouter/free",
        base_url="https://openrouter.ai/api/v1",
        api_key="test-openrouter-key",
    )


def test_build_pixelle_command_includes_backend_and_prompt_overrides(
    tmp_path: Path,
) -> None:
    plan = plan_media_request(
        "hazme algo para tiktok de una herramienta de ia que ahorra tiempo",
        optimizer_runner=None,
    )
    backend = BackendConfig(
        backend="openrouter",
        model="openrouter/free",
        base_url="https://openrouter.ai/api/v1",
        api_key="test-openrouter-key",
    )

    command = build_pixelle_command(
        plan=plan,
        backend_config=backend,
        output_dir=tmp_path,
        timestamp="20260520_161500",
    )

    assert command[0].endswith(("/.venv/bin/python", "/python3", "/python"))
    assert command[1].endswith("/PIXELLE_VIDEO/generate_video.py")
    assert "--script-brief" in command
    assert "--llm-base-url" in command
    assert "--llm-api-key" in command
    assert "--timestamp" in command
    assert "openrouter/free" in command


def test_run_pixelle_worker_returns_structured_success_result(tmp_path: Path) -> None:
    recorded: dict[str, list[str]] = {}
    plan = plan_media_request(
        "hazme algo para tiktok de una herramienta de ia que ahorra tiempo",
        optimizer_runner=None,
    )
    backend = BackendConfig(
        backend="openrouter",
        model="openrouter/free",
        base_url="https://openrouter.ai/api/v1",
        api_key="test-openrouter-key",
    )

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        recorded["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = run_pixelle_worker(
        plan=plan,
        output_dir=tmp_path,
        timestamp="20260520_161500",
        backend_resolver=lambda _backend, _model: backend,
        command_runner=fake_runner,
    )

    assert result == PixelleRunResult(
        status="success",
        output_path=str(
            tmp_path / "pixelle_hazme_algo_para_tiktok_de_una_20260520_161500.mp4"
        ),
        metadata_path=str(
            tmp_path / "pixelle_hazme_algo_para_tiktok_de_una_20260520_161500.json"
        ),
        backend_used="openrouter",
        model_used="openrouter/free",
        optimized_prompt=plan.optimized_prompt,
        error=None,
    )
    timestamp_index = recorded["command"].index("--timestamp")
    assert recorded["command"][timestamp_index + 1] == "20260520_161500"


def test_run_pixelle_worker_surfaces_error_excerpt_on_failure(tmp_path: Path) -> None:
    plan = plan_media_request("quiero un short de amazon sobre un producto útil para oficina", optimizer_runner=None)

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="httpx.ConnectError: sandbox blocked network access",
        )

    result = run_pixelle_worker(
        plan=plan,
        output_dir=tmp_path,
        timestamp="20260520_171000",
        backend_resolver=lambda _backend, _model: BackendConfig(
            backend="ollama",
            model="qwen2.5:1.5b",
            base_url=None,
            api_key=None,
        ),
        command_runner=fake_runner,
    )

    assert result == PixelleRunResult(
        status="failed",
        output_path=str(
            tmp_path / "pixelle_quiero_un_short_de_amazon_sobr_20260520_171000.mp4"
        ),
        metadata_path=str(
            tmp_path / "pixelle_quiero_un_short_de_amazon_sobr_20260520_171000.json"
        ),
        backend_used="ollama",
        model_used="qwen2.5:1.5b",
        optimized_prompt=plan.optimized_prompt,
        error="httpx.ConnectError: sandbox blocked network access",
    )
