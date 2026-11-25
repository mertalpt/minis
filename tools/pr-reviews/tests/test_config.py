import re
from pathlib import Path

import pytest

from pr_reviews import config

README = Path(__file__).parent.parent / "README.md"


def test_readme_example_parses() -> None:
    [example] = re.findall(r"```toml\n(.*?)```", README.read_text(), re.S)
    cfg = config.parse(example, source="README.md")
    assert cfg.repos


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(config.ConfigError, match="limit"):
        config.parse("limit = 5", source="test")


def test_missing_named_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="not found"):
        config.load(tmp_path / "missing.toml", required=True)
    assert config.load(tmp_path / "missing.toml", required=False) == config.Config()
