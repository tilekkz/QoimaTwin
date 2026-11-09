"""Backend-only Mercury configuration. No client-controlled endpoint or credentials."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ENDPOINT = "https://api.inceptionlabs.ai/v1/chat/completions"
_ENV_KEYS = frozenset(
    {"INCEPTION_API_KEY", "MERCURY_MODEL", "MERCURY_TIMEOUT_S", "MERCURY_MAX_COMPLETION_TOKENS"}
)
_MAX_ENV_BYTES = 16 * 1024


def _parse_env_file(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if key not in _ENV_KEYS:
            # Recognize a malformed known assignment without accepting shell syntax.
            if re.match(r"(?:" + "|".join(sorted(_ENV_KEYS)) + r")\b", line):
                raise ValueError
            continue
        if not separator or key in values:
            raise ValueError
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0] or value[0] in value[1:-1]:
                raise ValueError
            value = value[1:-1]
        elif value.endswith(("'", '"')):
            raise ValueError
        values[key] = value
    return values


def _read_env_file(path: Path) -> dict[str, str]:
    try:
        with path.open("rb") as stream:
            content = stream.read(_MAX_ENV_BYTES + 1)
        if len(content) > _MAX_ENV_BYTES:
            raise ValueError
        return _parse_env_file(content.decode("utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, ValueError):
        pass
    # Raise outside the handler so exception chains cannot expose paths or values.
    raise ValueError("invalid Mercury backend configuration file")


@dataclass(frozen=True, slots=True)
class MercurySettings:
    api_key: str | None = field(default=None, repr=False)
    model: str = "mercury-3"
    timeout_s: float = 10.0
    max_completion_tokens: int = 1024

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.model):
            raise ValueError("invalid Mercury model configuration")
        if not math.isfinite(self.timeout_s) or not 0 < self.timeout_s <= 30:
            raise ValueError("Mercury timeout must be greater than 0 and at most 30 seconds")
        if (
            type(self.max_completion_tokens) is not int
            or not 1 <= self.max_completion_tokens <= 4096
        ):
            raise ValueError("Mercury completion budget must be 1..4096 tokens")

    @classmethod
    def from_env(cls, *, env_file: Path | None = None) -> MercurySettings:
        """Load a trusted server path only if supplied; process environment takes precedence."""
        values = _read_env_file(env_file) if env_file is not None else {}
        values.update({key: os.environ[key] for key in _ENV_KEYS if key in os.environ})
        try:
            return cls(
                api_key=values.get("INCEPTION_API_KEY"),
                model=values.get("MERCURY_MODEL", "mercury-3"),
                timeout_s=float(values.get("MERCURY_TIMEOUT_S", "10")),
                max_completion_tokens=int(values.get("MERCURY_MAX_COMPLETION_TOKENS", "1024")),
            )
        except (ValueError, TypeError):
            pass
        raise ValueError("invalid Mercury backend configuration")
