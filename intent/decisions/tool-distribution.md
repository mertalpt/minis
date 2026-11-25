# Tool distribution

Facing users who want to run a tool with one command that needs no setup and
leaves nothing to clean up, we run tools with `uvx` from this repository's git,
unversioned, rather than tagging releases or publishing to PyPI, to keep
running a tool to one line and the repository free of release machinery,
accepting that every run uses the newest `main`.

## Governs

- `tools/**`

## Context

- The users are the maintainer and teammates on Ubuntu 24.04 and 26.04 laptops
  with `uv` installed.
- `uvx --from "git+<repository>#subdirectory=tools/<name>" <name>` builds the
  tool into uv's cache and runs it, fetching the branch head on every run. What
  it leaves behind is in uv's cache, which `uv cache clean` removes.
- uv downloads a Python when no Python on the machine satisfies the tool's
  `requires-python`. Ubuntu 24.04's system Python is 3.12.
- While the repository is private, running a tool needs read access to it and
  git credentials for GitHub.

## Decision

- A tool runs with
  `uvx --from "git+https://github.com/mertalpt/minis#subdirectory=tools/<name>" <name>`,
  or stays installed with `uv tool install` from the same source.
- Tools are not tagged or published. The `version` in a tool's
  `pyproject.toml` is informational.
- A tool sets `requires-python = ">=3.12"` unless it needs a newer Python, so
  that Ubuntu's system Python runs it without a download.
- `main` stays runnable: a tool's checks pass in CI before it reaches `main`.

## Consequences

- A change merged to `main` reaches every user on their next run.
- A user can pin a tool to a commit by adding `@<commit>` to the git URL.
- Per-tool tags can be added later; the commands gain `@<name>-v<version>` and
  no files move.

## Alternatives

- Per-tool tags and releases, as in `mertalpt/agent-collections`: pinnable, but
  they need release automation, and the users want the newest version.
- Publishing to PyPI: shortens the command, but adds publishing and naming
  overhead for tools meant for a few people.

## Revisit when

- A user needs to stay on an older version of a tool.
- A tool needs a runtime or system packages that uv cannot provide.
