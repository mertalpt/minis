# Contributing

This guide covers setting up the development environment, the conventions for
commits and pull requests, adding a tool, and the repository settings that live
on GitHub.

## Setup

Development happens in the Workshop defined by `.workshop/minis.yaml`; see
[`docs/agents/environment.md`](docs/agents/environment.md). Inside it, enable
the hooks and deploy the agent customizations:

```bash
pre-commit install
apm install
```

`apm install` deploys the collections pinned in `apm.yml` and `apm.lock.yaml`
to `.claude/`. The deployed files are ignored by Git, so rerun it after a fresh
clone or after changing the pins.

## Commits and pull requests

Changes reach `main` through pull requests, which are squash-merged, so the
pull request title becomes the commit subject on `main`.

Titles and commit subjects follow Conventional Commits:
`<type>[(<scope>)][!]: <subject>`, such as `feat(<name>): add a --json flag`.
The scope of a change to a tool is the tool's name.

## Decision records

Decisions that the code does not show live in
[`intent/decisions/`](intent/decisions/), one mutable record per topic,
managed with the `intent` collection's `intent-decisions` skill. The
pre-commit hook and CI check them.

## Adding a tool

The layout of a tool is set by the
[tool layout](intent/decisions/tool-layout.md) record. Create one with uv,
replacing `<name>` with the tool's name:

```bash
cd tools
uv init --package --python 3.12 --author-from none <name>
cd <name>
uv add --dev --bounds major mypy pytest ruff
```

Then:

1. Set the lower bound of each dependency to the first release of its line,
   such as `ruff>=0.17.0,<0.18.0` or `mypy>=2.0.0,<3.0.0`, and run `uv lock`.
2. Append the tool configuration to `pyproject.toml`:

   ```toml
   [tool.ruff.lint]
   select = ["E", "W", "F", "I", "B", "UP", "D"]

   [tool.ruff.lint.pydocstyle]
   convention = "google"

   [tool.ruff.lint.per-file-ignores]
   "tests/**" = ["D"]

   [tool.mypy]
   strict = true

   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ```

3. Add `tox.toml`:

   ```toml
   requires = ["tox>=4.21", "tox-uv>=1"]
   env_list = ["lint", "static", "unit"]

   [env_run_base]
   runner = "uv-venv-lock-runner"
   dependency_groups = ["dev"]

   [env.format]
   description = "Apply formatting and import sorting"
   skip_install = true
   commands = [["ruff", "check", "--select", "I", "--fix"], ["ruff", "format"]]

   [env.lint]
   description = "Check formatting and lint"
   skip_install = true
   commands = [["ruff", "format", "--check"], ["ruff", "check"]]

   [env.static]
   description = "Type-check"
   commands = [["mypy", "src", "tests"]]

   [env.unit]
   description = "Run unit tests"
   commands = [["pytest", { replace = "posargs", extend = true }]]
   ```

4. Write the `description` in `pyproject.toml` and the tool's `README.md`: what
   the tool does and the command that runs it. Add a row for the tool to the
   table in the root [`README.md`](README.md).
5. Write the tool in `src/` and its tests in `tests/`, then run the checks from
   the tool's directory:

   ```bash
   uvx tox -e format,lint,static,unit
   ```

CI runs `lint`, `static`, and `unit` on Python 3.12 and the newest Python for
every tool that a pull request changes.

## Repository settings

Some of how this repository behaves is configured on GitHub rather than in the
source, and does not travel with a clone:

- The default branch carries a ruleset that requires a pull request and a
  linear history, and refuses deletion and non-fast-forward pushes. It
  requires the `check` job of the `Decision records` workflow and the `result`
  job of the `Tools` workflow to pass.
- Pull requests are squash-merged.
- Dependency graph, Dependabot alerts, and Dependabot security updates are
  enabled, which is what makes `.github/dependabot.yaml` take effect.
