# Tool layout

Facing a repository of small, unrelated programs, we give each tool its own
uv project under `tools/<name>/` rather than sharing a uv workspace, a
package, or a single-file script format, to keep each tool self-contained in
its dependencies, checks, and installation, accepting configuration repeated
in every tool.

## Governs

- `tools/**`

## Context

- The tools are small command-line programs, mostly in Python, that share no
  code.
- Each tool is run or installed from its own directory, as described in
  [tool-distribution](tool-distribution.md).

## Decision

- Each tool lives in `tools/<name>/`, where `<name>` is the directory, the
  distribution name in `pyproject.toml`, and the command in
  `[project.scripts]`.
- Each tool is a uv project with its own `pyproject.toml`, `uv.lock`,
  `tox.toml`, `README.md`, `src/` package, and `tests/`.
- Tools import nothing from one another or from shared code in this
  repository.
- Each tool's `tox.toml` provides `format`, `lint`, `static`, and `unit`
  environments. CI runs `lint`, `static`, and `unit` for every tool that a
  pull request changes.
- Conventions and CI cover Python only. The layout itself assumes no
  language, so a tool in another language fits under `tools/<name>/` once
  conventions for it exist.

## Consequences

- Adding a tool repeats the configuration from the recipe in
  `CONTRIBUTING.md`, and changing a shared convention means editing every
  tool.
- Tools may depend on different versions of the same package.
- A change to one tool runs only that tool's checks.

## Alternatives

- A uv workspace: its single lock puts every tool on the same dependency
  versions, coupling unrelated tools.
- Single-file scripts with inline metadata (PEP 723): the least boilerplate,
  but tests and multi-module tools are awkward, and the repository would
  carry two conventions.
- One package with an entry point per tool: couples the dependencies of
  unrelated tools.

## Revisit when

- Tools start to need shared code.
- A tool in a language other than Python is added.
- Keeping the repeated configuration in sync across tools becomes a burden.
