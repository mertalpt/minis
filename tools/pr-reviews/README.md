# pr-reviews

Lists the open pull requests on GitHub.com that wait for your review, ranked
so that overdue ones come first and small ones rise quickly. The ranking rules
and their reasons are in the
[PR review queue](../../intent/decisions/pr-reviews-queue.md) decision record.

## Usage

```bash
uvx --from "git+https://github.com/mertalpt/minis#subdirectory=tools/pr-reviews" pr-reviews queue
```

With git credentials for GitHub over SSH instead of HTTPS:

```bash
uvx --from "git+ssh://git@github.com/mertalpt/minis#subdirectory=tools/pr-reviews" pr-reviews queue
```

The tool only reads from GitHub. It uses the first GitHub token it finds in:

1. the `GH_TOKEN` environment variable,
2. the `GITHUB_TOKEN` environment variable,
3. `gh auth token`, after `gh auth login`.

An SSH key alone is not enough, because the GitHub API needs a token. If no
token is found or GitHub rejects it, the tool prints an error and exits with
status 1. The queue shows only what the token can read: a fine-grained token
limited to some repositories hides requests in the others, and an
organization that enforces SAML single sign-on needs the token authorized for
it. Requests the token cannot read are reported as warnings.

## `queue`

`pr-reviews queue` lists the open, non-draft pull requests whose review is
requested from you, directly or through a team you belong to.

| Flag | Effect |
| --- | --- |
| `--owner OWNER` | Only include repositories of this organization or user. Repeatable. |
| `--exclude-owner OWNER` | Exclude repositories of this organization or user. Repeatable. |
| `--direct-only` | Only include requests made to you directly, not through a team. |
| `--hide-approved` | Hide pull requests that GitHub reports as approved. |
| `--limit-days DAYS` | Working days after which a pull request is overdue. Default: 8. |
| `--top N` | Show only the N highest-ranked pull requests; `0` shows all. Default: 20. |
| `--json` | Print a JSON array instead of a table. |
| `--config PATH` | Read this configuration file instead of the default one. |

The table has an `Overdue` section and a `Queue` section, each in ranked
order. Each pull request takes two lines: the columns below, then its full
URL.

| Column | Meaning |
| --- | --- |
| `SCORE` | The priority: size score plus time score. |
| `SIZE` | Lines changed outside ignored files. |
| `WAITED` | Working days waited, as described under [Scoring](#scoring). |
| `REQUEST` | `direct` if your review was requested from you, `team` if only through a team. `(+)` follows if the pull request is approved. |
| `PR` | `owner/repo#number`. On a terminal, it is also a link to the pull request. |
| `TITLE` | The title. |

A pull request is approved when GitHub's review decision is `APPROVED`: it
has the approving reviews the repository's branch protection requires.
Submitting a review removes your request, so these approvals are usually
from others.

On a terminal, titles are shortened to fit its width, URLs are dimmed, and
`(+)` is green. Setting `NO_COLOR` turns the styling off. When
the output is not a terminal, titles are kept whole and nothing is styled.

`--json` prints the same information, with one object per pull request in
ranked order, using the keys `rank`, `overdue`, `priority`, `size_score`,
`time_score`, `size`, `size_bucket`, `wait_days`, `waiting_since`, `ref`,
`owner`, `repo`, `number`, `title`, `url`, `request`, and `approved`.

## Configuration

The tool reads `$XDG_CONFIG_HOME/pr-reviews/config.toml`, by default
`~/.config/pr-reviews/config.toml`, if it exists. Every key is optional:

```toml
limit_days = 8          # working days until a pull request is overdue
top = 20                # as --top
direct_only = false     # as --direct-only
hide_approved = false   # as --hide-approved
include_owners = []     # as --owner; flags add to this list
exclude_owners = []     # as --exclude-owner; flags add to this list
# Replaces the default ignore patterns listed below.
ignore = ["uv.lock", "package-lock.json", "poetry.lock"]

# Added to the global ignore patterns for one repository.
[repos."acme/app"]
ignore = ["generated/**", "*.snap"]
```

Unknown keys are an error. Owners and repositories compare without regard to
case.

## Scoring

The **wait** starts when the pull request was last marked ready for review, or
when it was created if it never was a draft. It runs continuously except on
Saturdays and Sundays in the local time zone of the machine running the tool.
A working day is 24 hours of weekday time. Public holidays count as working
time.

The **size** is lines added plus lines deleted, leaving out files that match
an ignore pattern. A pattern without a `/` matches the file name in any
directory; a pattern with a `/` matches the whole path from the repository
root, where `*` also matches across `/`. The default patterns are `uv.lock`,
`poetry.lock`, `Pipfile.lock`, `pdm.lock`, `package-lock.json`,
`npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lock`,
`Cargo.lock`, `Gemfile.lock`, `composer.lock`, and `go.sum`.

The **size score**:

| Lines changed | <100 | <200 | <300 | <500 | <800 | <1300 | <2100 | >=2100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Size score | 21 | 20 | 19 | 18 | 16 | 13 | 8 | 0 |

The **time score** splits the wait from 0 to the limit into 8 equal steps,
scoring 0, 1, 2, 3, 5, 8, 13, and 21. With the default limit of 8 working
days, each step is one working day: a pull request at 3.5 days scores 3, and
one at 7.5 days scores 21.

A pull request is **overdue** when its wait is equal to or longer than the
limit. The queue lists overdue pull requests first, oldest first, then the
rest by priority, highest first. Equal priorities are listed oldest first.
Approved pull requests keep their place. Every request is fetched and
ranked; `--top` only limits how many are shown, in the table and in
`--json`.

## Known gaps

- Once you submit a review, GitHub removes your request, and the pull request
  leaves your queue until your review is requested again.
- GitHub search returns at most 1000 results per query, and lists at most
  3000 changed files per pull request; beyond those, requests are missing and
  ignored files are counted.
- Generated files count toward the size unless a pattern matches them.
- Weekends are Saturday and Sunday in the machine's time zone, for every
  reviewer and author.
- Only GitHub.com is supported.
- Titles with wide characters, such as emoji or CJK text, can shift the
  table's alignment and overflow the terminal width.
