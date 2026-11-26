# minis

Small, self-contained programs, mostly Python command-line tools. Each tool
runs with one command and needs nothing installed but
[uv](https://docs.astral.sh/uv/).

## Running a tool

```bash
uvx --from "git+https://github.com/mertalpt/minis#subdirectory=tools/<name>" <name> [args]
```

Every run uses the newest version on `main`. To keep a tool installed instead,
run `uv tool install` with the same source, and update it with
`uv tool upgrade <name>`. `uv cache clean` removes what `uvx` leaves behind.

The repository is private for now, so running a tool needs read access to it
and git credentials for GitHub, such as those `gh auth setup-git` configures.
With git set up for SSH instead:

```bash
uvx --from "git+ssh://git@github.com/mertalpt/minis#subdirectory=tools/<name>" <name> [args]
```

## Tools

Each tool's `README.md` in `tools/<name>/` describes it.

| Tool | Description |
| --- | --- |
| [`pr-reviews`](tools/pr-reviews/) | Lists the GitHub pull requests waiting for your review, ranked by size and wait, and shows your review karma: lines reviewed against lines authored. |

## Repository Structure

| Directory | Description |
| --- | --- |
| `.claude/` | Holds Claude Code settings. The rules and skills that `apm install` deploys here are ignored by Git. |
| `.github/` | Holds GitHub configuration: CI workflows, Dependabot, and the issue and pull request templates. |
| `.workshop/` | Holds the [Workshop](https://ubuntu.com/workshop) definition and in-project SDKs of the development container. |
| `docs/` | Holds documentation for developing the repository. |
| `intent/` | Holds the repository's [decision records](intent/decisions/) and their configuration. |
| `scripts/` | Holds scripts used to manage the repository itself. |
| `tools/` | Holds one directory per tool. |

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
