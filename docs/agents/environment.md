# Agent environment

This document describes the environment an agent works in on this repository:
how to tell whether you are running inside the Workshop container, what the
container provides, and what the GitHub token you hold can reach.

## Where you are running

Development normally happens inside a Workshop container defined by
`.workshop/minis.yaml`. The container exists when `/var/lib/workshop` is
present; if that directory is absent, you are on a host and nothing in this
section applies.

Inside the container:

- `/project` is the working tree, mounted from the host. Its `.git/config` is
  therefore the host's file: changes to remotes or repository git settings are
  visible to the host and outlive the container.
- The SDKs in `.workshop/minis.yaml` provide `claude`, `gh`, `apm`,
  `pre-commit`, `uv`, and `uvx`. The `uv` SDK keeps uv's cache on the host, so
  it survives a refresh.
- `tox` is not installed. Run it with `uvx tox` from a tool's directory.
- Do not install uv from the `astral-uv` snap. Started through the snap
  launcher, uv loses output written to a file, and the Python processes it
  starts exit with code 120.

The `actions` declared in `.workshop/minis.yaml` are invoked from the host as
`workshop run <action>` and cannot be run from inside the container:

| Action | Purpose |
| --- | --- |
| `status` | Report `gh` and `claude` authentication, the git identity, tool versions, and git remotes |
| `gh-auth` | Authenticate `gh` and install its git credential helper |
| `git-identity` | Set the global git identity |
| `claude-auth` | Authenticate `claude` |
| `claude-skip-permissions` | Start `claude` with permission checks bypassed |

When one of these is needed, ask the operator to run it rather than attempting
an equivalent yourself.

## What you can do in this repository

You authenticate with a fine-grained personal access token, scoped to this
repository alone and carrying an expiry.

| Permission | Access | Reach |
| --- | --- | --- |
| Contents (`code`) | Read and write | Push branches. GitHub bundles several repository write operations here. |
| Workflows | Read and write | Push changes under `.github/workflows/` |
| Issues | Read and write | The issue tracker |
| Pull requests | Read and write | Open and comment on pull requests |
| Actions | Read | Workflow run results |
| Dependabot alerts | Read | Alerts against the ecosystems in `.github/dependabot.yaml` |
| Metadata | Read | Mandatory on any fine-grained token |

Repository administration is not granted. Repository settings and rulesets,
listed in [`CONTRIBUTING.md`](../../CONTRIBUTING.md#repository-settings),
cannot be changed with this token, and should not be worked around. Never merge
a pull request: merging is the repository owner's decision.

GitHub Actions reports through the Checks API, which fine-grained tokens cannot
read at any permission level. `gh pr checks` and
`gh pr view --json statusCheckRollup` fail with a 403. Read run results from
`gh api repos/{owner}/{repo}/actions/runs` instead.
