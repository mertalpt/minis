# pr-reviews

Lists the open pull requests on GitHub.com that wait for your review, ranked
so that overdue ones come first and small ones rise quickly, and shows your
review karma: the lines you recently reviewed against the lines you recently
authored. The rules and their reasons are in the
[PR review queue](../../intent/decisions/pr-reviews-queue.md) and
[PR review karma](../../intent/decisions/pr-reviews-karma.md) decision
records.

## Usage

```bash
uvx --from "git+https://github.com/mertalpt/minis#subdirectory=tools/pr-reviews" pr-reviews queue
```

With git credentials for GitHub over SSH instead of HTTPS:

```bash
uvx --from "git+ssh://git@github.com/mertalpt/minis#subdirectory=tools/pr-reviews" pr-reviews queue
```

Replace `queue` with `karma` to show your karma.

The tool only reads from GitHub. It uses the first GitHub token it finds in:

1. the `GH_TOKEN` environment variable,
2. the `GITHUB_TOKEN` environment variable,
3. `gh auth token`, after `gh auth login`.

An SSH key alone is not enough, because the GitHub API needs a token. If no
token is found or GitHub rejects it, the tool prints an error and exits with
status 1. The tool sees only what the token can read: a fine-grained token
limited to some repositories hides pull requests in the others, and an
organization that enforces SAML single sign-on needs the token authorized for
it. Pull requests the token cannot read are reported as warnings.

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
| `WAITED` | Working days waited, as described under [Queue scoring](#queue-scoring). |
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

## `karma`

`pr-reviews karma` divides the lines of the pull requests you recently
reviewed by the lines of those you recently authored, with newer work
weighing more. It is for checking your own balance between the work you put
out and the reviews you give back.

```text
Karma     1.84  (target 2)

          WEIGHTED  LINES  PRS
Reviewed      1234   1890    7
Authored       671    720    3

Window    10 working days, full weight for 2
```

| Flag | Effect |
| --- | --- |
| `--owner OWNER` | Only count repositories of this organization or user. Repeatable. |
| `--exclude-owner OWNER` | Do not count repositories of this organization or user. Repeatable. |
| `--full-weight-days DAYS` | Working days during which work keeps full weight, F. Default: 2. |
| `--window-days DAYS` | Working days after which work no longer counts, N. Default: 10. |
| `--target KARMA` | The karma you aim for, shown beside the figure. Default: none. |
| `--list` | Also list the counted pull requests under the summary. |
| `--json` | Print a JSON object instead of the summary. |
| `--config PATH` | Read this configuration file instead of the default one. |

F must be less than N after flags override the configuration; otherwise the
tool prints an error and exits with status 1.

**Reviewed work** is every pull request by someone else on which you
submitted at least one review: an approval, a request for changes, or a
comment. Each counts once, dated at your first submitted review. Reviews on
your own pull requests never count, including the comment reviews GitHub
creates when you reply in review threads.

**Authored work** is every pull request you opened that is not a draft now,
whether open, merged, or closed without merging. It is dated at when it was
last marked ready for review, or at its creation if it never was a draft.

**Lines** are the lines added plus the lines deleted, as GitHub reports them
when the tool runs, leaving out files that match the ignore patterns, as for
the queue's size.

**Age** is the working time since the date, measured like the queue's wait:
continuously, except on Saturdays and Sundays in the machine's local time
zone, with 24 hours of weekday time as one working day.

**Weight** depends on the age:

| Age in working days | Weight |
| --- | --- |
| F or less | 1 |
| Between F and N | 1 - ((age - F) / (N - F))^2 |
| N or more | Not counted |

With the defaults, work weighs 1 for its first 2 working days, 0.94 at 4,
0.75 at 6, 0.23 at 9, and drops out at 10.

**Karma** is the sum of weight times lines over reviewed work, divided by the
same sum over authored work. When no authored lines fall in the window, the
summary shows `-` and says so, and `--json` gives `null`.

For each side, the summary gives the weighted lines, rounded, the lines
before weighting, and the number of pull requests counted. Owner filters from the configuration and flags apply to
both sides.

`--list` adds a table for each side, newest first, with each counted pull
request's lines, weight, age in working days, the date it is counted from in
the machine's local time, and its URL.

`--json` prints an object with the keys `karma`, `target`, `window_days`,
`full_weight_days`, `reviewed`, and `authored`. `reviewed` and `authored`
each hold `weighted_lines`, `lines` (unweighted), `prs`, and
`pull_requests`, one object per
counted pull request, newest first, with the keys `ref`, `url`, `lines`,
`date`, `age_days`, and `weight`.

### Reading karma

Karma of 1 means you reviewed as many weighted lines as you authored. When
pull requests need several approvals, the team's work flows only if each
person reviews more than they author: with two required approvals, a
balanced person has karma of about 2. Pick a target that fits you, such as
your team's required approvals or another value for your role. Below the
target, you author more than you review in return; above it, you review
more.

Karma is an approximation. A single large pull request on either side moves
it a lot, and it changes day by day as work ages out of the window.

## Configuration

The tool reads `$XDG_CONFIG_HOME/pr-reviews/config.toml`, by default
`~/.config/pr-reviews/config.toml`, if it exists. Every key is optional:

```toml
limit_days = 8          # working days until a pull request is overdue
top = 20                # as --top
direct_only = false     # as --direct-only
hide_approved = false   # as --hide-approved
include_owners = []     # as --owner, for queue and karma; flags add to this list
exclude_owners = []     # as --exclude-owner, for queue and karma; flags add to this list
# Replaces the default ignore patterns listed below.
ignore = ["uv.lock", "package-lock.json", "poetry.lock"]

# Added to the global ignore patterns for one repository.
[repos."acme/app"]
ignore = ["generated/**", "*.snap"]

[karma]
full_weight_days = 2    # as --full-weight-days
window_days = 10        # as --window-days
target = 2.0            # as --target; unset by default
```

The ignore patterns apply to the queue's size and to karma's lines.

Unknown keys are an error. Owners and repositories compare without regard to
case.

## Queue scoring

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
  3000 changed files per pull request; beyond those, pull requests are
  missing and ignored files are counted.
- Generated files count toward the size unless a pattern matches them.
- Weekends are Saturday and Sunday in the machine's time zone, for every
  reviewer and author.
- Only GitHub.com is supported.
- Karma searches the pull requests updated since shortly before the window.
  Submitting a comment review is known to update a pull request; that
  approvals, requests for changes, and marking a pull request ready for
  review do the same is assumed.
- Karma counts a pull request's lines when the tool runs, not when you
  reviewed it, so one that grows after your review counts its new size.
- Karma counts a comment review the same as an approval, whatever its
  depth.
- Titles with wide characters, such as emoji or CJK text, can shift the
  table's alignment and overflow the terminal width.
