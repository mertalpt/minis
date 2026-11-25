"""The user's configuration file."""

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, ValidationError

DEFAULT_IGNORE: tuple[str, ...] = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "pdm.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
    "go.sum",
)


class ConfigError(Exception):
    """The configuration file cannot be read or is invalid."""


class RepoConfig(BaseModel):
    """Settings for one `owner/repo`."""

    model_config = ConfigDict(extra="forbid")

    ignore: list[str] = []


class Config(BaseModel):
    """The tool's configuration."""

    model_config = ConfigDict(extra="forbid")

    limit_days: PositiveFloat = 8
    direct_only: bool = False
    hide_approved: bool = False
    include_owners: list[str] = []
    exclude_owners: list[str] = []
    ignore: list[str] = Field(default_factory=lambda: list(DEFAULT_IGNORE))
    repos: dict[str, RepoConfig] = {}


def default_path() -> Path:
    """Return the configuration path under the XDG config directory."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "pr-reviews" / "config.toml"


def load(path: Path, *, required: bool) -> Config:
    """Read the configuration file.

    Args:
        path: The file to read.
        required: Whether a missing file is an error rather than defaults.

    Returns:
        The configuration.

    Raises:
        ConfigError: The file is missing while required, or is invalid.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if required:
            raise ConfigError(f"{path}: file not found") from None
        return Config()
    except OSError as e:
        raise ConfigError(f"{path}: {e.strerror}") from None
    return parse(text, source=str(path))


def parse(text: str, *, source: str) -> Config:
    """Parse configuration from TOML text.

    Raises:
        ConfigError: The text is not valid TOML or not a valid configuration.
    """
    try:
        return Config.model_validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{source}: {e}") from None
    except ValidationError as e:
        raise ConfigError(f"{source}: {e}") from None
