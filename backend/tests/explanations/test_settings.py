from __future__ import annotations

import importlib
import os
import traceback
from pathlib import Path
from typing import IO, Any

import httpx
import pytest

import app.explanations.settings as settings_module
from app.explanations import (
    ExplanationError,
    MercurySettings,
    explain_comparison,
    extract_comparison_facts,
)


@pytest.fixture(autouse=True)
def fabricated_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    return environment


def test_explicit_file_and_environment_precedence(
    tmp_path: Path, fabricated_environment: dict[str, str]
) -> None:
    config = tmp_path / "fabricated.env"
    config.write_text(
        "# fabricated settings\n\nINCEPTION_API_KEY='fabricated-file-key'\n"
        'MERCURY_MODEL="mercury-2.5"\nMERCURY_TIMEOUT_S=2\n'
        "MERCURY_MAX_COMPLETION_TOKENS=123\nOTHER_SETTING=ignored\n",
        encoding="utf-8-sig",
    )
    settings = MercurySettings.from_env(env_file=config)
    assert settings.api_key == "fabricated-file-key"
    assert settings.model == "mercury-2.5"
    assert settings.timeout_s == 2
    assert settings.max_completion_tokens == 123
    fabricated_environment.update(
        INCEPTION_API_KEY="fabricated-process-key",
        MERCURY_MODEL="mercury-3",
        MERCURY_TIMEOUT_S="3",
        MERCURY_MAX_COMPLETION_TOKENS="456",
    )
    settings = MercurySettings.from_env(env_file=config)
    assert settings.api_key == "fabricated-process-key"
    assert settings.model == "mercury-3"
    assert settings.timeout_s == 3
    assert settings.max_completion_tokens == 456
    assert "fabricated" not in repr(settings)
    assert fabricated_environment["INCEPTION_API_KEY"] == "fabricated-process-key"


def test_default_never_discovers_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("INCEPTION_API_KEY=fabricated-key", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert MercurySettings.from_env().api_key is None
    assert MercurySettings.from_env().model == "mercury-3"
    assert MercurySettings.from_env(env_file=tmp_path / "missing.env").api_key is None


@pytest.mark.parametrize("value", ["", "  ", '""', "'   '"])
def test_empty_file_key_is_unavailable(
    tmp_path: Path, comparison: dict[str, object], value: str
) -> None:
    config = tmp_path / "fabricated.env"
    config.write_text(f"INCEPTION_API_KEY={value}\n", encoding="utf-8")
    settings = MercurySettings.from_env(env_file=config)
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("network called"))) as c,
        pytest.raises(ExplanationError, match="unavailable"),
    ):
        explain_comparison("id", extract_comparison_facts(comparison), settings=settings, client=c)


def test_empty_environment_key_overrides_file(
    tmp_path: Path, fabricated_environment: dict[str, str]
) -> None:
    config = tmp_path / "fabricated.env"
    config.write_text("INCEPTION_API_KEY=fabricated-key", encoding="utf-8")
    fabricated_environment["INCEPTION_API_KEY"] = ""
    assert MercurySettings.from_env(env_file=config).api_key == ""


@pytest.mark.parametrize(
    "content",
    [
        "INCEPTION_API_KEY fabricated-secret",
        'INCEPTION_API_KEY="fabricated-secret',
        "INCEPTION_API_KEY='fabricated-secret\"",
        "INCEPTION_API_KEY=fabricated-secret\nINCEPTION_API_KEY=duplicate",
        "MERCURY_MODEL=mercury-3\nMERCURY_MODEL=mercury-3",
        "MERCURY_TIMEOUT_S=fabricated-secret",
        "MERCURY_MAX_COMPLETION_TOKENS=fabricated-secret",
        "MERCURY_MODEL=fabricated-secret!",
        "MERCURY_TIMEOUT_S=nan",
        "MERCURY_MAX_COMPLETION_TOKENS=0",
    ],
)
def test_invalid_known_settings_have_safe_errors(tmp_path: Path, content: str) -> None:
    config = tmp_path / "fabricated-secret.env"
    config.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="Mercury") as caught:
        MercurySettings.from_env(env_file=config)
    assert "fabricated-secret" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None


def test_file_is_validated_even_if_environment_overrides(
    tmp_path: Path, fabricated_environment: dict[str, str]
) -> None:
    config = tmp_path / "fabricated.env"
    config.write_text("INCEPTION_API_KEY=first\nINCEPTION_API_KEY=second", encoding="utf-8")
    fabricated_environment["INCEPTION_API_KEY"] = "fabricated-process-key"
    with pytest.raises(ValueError):
        MercurySettings.from_env(env_file=config)


@pytest.mark.parametrize("content", [b"#" + b"x" * 16384, b"INCEPTION_API_KEY=\xff"])
def test_size_and_encoding_fail_safely(tmp_path: Path, content: bytes) -> None:
    config = tmp_path / "fabricated-secret.env"
    config.write_bytes(content)
    with pytest.raises(ValueError) as caught:
        MercurySettings.from_env(env_file=config)
    assert "fabricated-secret" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None


def test_exact_size_limit_and_literal_values(tmp_path: Path) -> None:
    config = tmp_path / "fabricated.env"
    content = 'INCEPTION_API_KEY="${FABRICATED}=$(echo fabricated)=literal"\n'
    content += "#" + "x" * (16384 - len(content) - 1)
    config.write_bytes(content.encode("utf-8"))
    assert MercurySettings.from_env(env_file=config).api_key == (
        "${FABRICATED}=$(echo fabricated)=literal"
    )


def test_unknown_lines_ignored_and_whitespace_supported(tmp_path: Path) -> None:
    config = tmp_path / "fabricated.env"
    config.write_text(
        "UNKNOWN='unterminated\nUNKNOWN=duplicate\nunknown malformed\n"
        '  # comment\n INCEPTION_API_KEY = "fabricated-key" \n',
        encoding="utf-8",
    )
    assert MercurySettings.from_env(env_file=config).api_key == "fabricated-key"


def test_unreadable_file_errors_do_not_echo_os_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: Any, **kwargs: Any) -> IO[bytes]:
        raise PermissionError("fabricated-secret")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(ValueError) as caught:
        MercurySettings.from_env(env_file=tmp_path / "fabricated.env")
    assert "fabricated-secret" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None


def test_import_performs_no_configuration_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("configuration read during import")

    class UnreadableEnvironment(dict[str, str]):
        get = unexpected
        __getitem__ = unexpected

    monkeypatch.setattr(Path, "open", unexpected)
    monkeypatch.setattr(os, "environ", UnreadableEnvironment())
    importlib.reload(settings_module)
