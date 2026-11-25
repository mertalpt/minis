# PR review queue

Facing pull requests that wait too long for review, we rank a reviewer's
pending review requests by a size score plus a time score, with an overdue
tier above them for requests past a deadline, rather than a single capped sum
or an age-only list, to steer authors toward smaller pull requests while
guaranteeing that every pull request reaches the top of the queue, accepting
fixed scoring tables that need retuning when the team's review habits change.

## Governs

- `tools/pr-reviews/**`

## Context

- Pull requests in the team wait too long for review. A workflow in the
  team's repositories requests reviews from people and teams until a pull
  request has its required approvals, and stops requesting once it has them.
  Most of its requests are team requests.
- In the team's experience, a change of a few lines takes seconds to review.
  Review quality holds up to about 500 lines, stays reasonable up to about
  1000, degrades beyond that, and is practically gone past about 2000.
  Shrinking a change from 250 lines to 100 gains little; shrinking one from
  1300 lines to 800 matters.
- A review takes about 5 working days on average.
- GitHub reports, per pull request, the lines added and deleted, the path and
  line counts of each changed file with no flag for generated files, the
  times it was created and marked ready for review, and a `reviewDecision`
  of `APPROVED`, `REVIEW_REQUIRED`, or `CHANGES_REQUESTED`.
- Which pull requests the tool sees is bounded by the user's GitHub
  credentials.
- GitHub search's `review-requested:` qualifier matches requests to the user
  and to teams the user is on, and `user-review-requested:` only direct
  requests. A user's request leaves the search results once they review.
- GraphQL lists each changed file with its path, so lines in files that match
  a pattern can be subtracted from the total. GraphQL returns partial data
  with errors for organizations the token is not authorized for, such as
  those enforcing SAML single sign-on.
- Users authenticate `gh` with `gh auth login`, which stores an API token even
  when git uses SSH, or provide a token in the environment.
- The tool is low-stakes and best effort: it serves the common case, and
  known gaps are documented rather than handled.

## Decision

- The queue holds open, non-draft pull requests in unarchived repositories on
  GitHub.com that request the user's review, directly or through a team,
  found by searching `review-requested:@me`. A request is direct when
  `user-review-requested:@me` also finds it, and through a team otherwise.
  Team requests are included by default; a flag excludes them.
- Filters include or exclude pull requests by repository owner, an
  organization or a user, compared without regard to case and applied to
  the search results rather than added to the search query. Flags add to the
  owners in the configuration.
- Configuration is a TOML file at `$XDG_CONFIG_HOME/pr-reviews/config.toml`,
  unknown keys rejected. It sets the limit, the owner filters, the defaults of
  the flags, and the ignore patterns.
- The token comes from `GH_TOKEN`, then `GITHUB_TOKEN`, then `gh auth token`.
  It is held in memory only. Requests go over HTTPS from the standard
  library, so `gh` is optional. GraphQL errors that come with partial data
  are printed as warnings; errors without data, a missing token, or HTTP 401
  end the run with status 1.
- Pull requests whose `reviewDecision` is `APPROVED` keep their rank and are
  marked; a flag hides them.
- The wait starts at the latest time the pull request was marked ready for
  review, or at its creation if it never was a draft. It is measured
  continuously, excluding Saturdays and Sundays in the local time zone of
  the machine running the tool. A working day is 24 hours of weekday time.
  Public holidays count as working time.
- The size is lines added plus lines deleted, excluding files that match
  path patterns. A pattern without `/` matches the file name in any
  directory; one with `/` matches the whole path. The global patterns
  replace the defaults, which cover common lock files; patterns for an
  `owner/repo` add to the global ones.
- The size score is 21 minus a Fibonacci number, so its drops grow with the
  size:

  | Lines changed | <100 | <200 | <300 | <500 | <800 | <1300 | <2100 | >=2100 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Size score | 21 | 20 | 19 | 18 | 16 | 13 | 8 | 0 |

- The deadline is a limit in working days, configurable, 8 by default. A
  pull request is overdue when its wait reaches the limit.
- The time score divides the wait from 0 to the limit into 8 equal steps
  scoring 0, 1, 2, 3, 5, 8, 13, and 21.
- Overdue pull requests come first, oldest first. The rest follow by size
  score plus time score, highest first. Equal scores order oldest first.
- The tool fetches and ranks every request, then shows the 20 highest-ranked
  by default, about what fits a full-height terminal at 1080p. A setting and
  a flag change the number or show all.

## Consequences

- Below 500 lines, size scores differ by at most 3 points, so waiting time
  decides the order. Above 800 lines, size decides it until the last steps
  before the deadline.
- A pull request of 2100 lines or more ties a fresh one under 100 lines just
  before its deadline, and passes it at the deadline.
- Once overdue, size no longer affects the order.
- If most pull requests wait past the limit, the overdue tier holds most of
  the queue and the order reduces to oldest first.
- A pull request waiting over a public holiday gains time score.
- Generated files that no pattern matches count toward the size.
- A pull request leaves the user's queue once they review it, until their
  review is requested again.
- Every pull request with more than 100 changed files costs one more query
  per further 100 files.
- Running the tool needs a GitHub token; an SSH key alone is not enough.

## Alternatives

- Size and time scores each capped at 21 and summed, with no deadline: a
  steady stream of small pull requests keeps a large stale one from the top
  indefinitely.
- An uncapped time score (aging): every pull request reaches the top, but
  the wait before it does follows from the scales rather than a stated
  limit, which is harder to explain to the team.
- Multiplying size and time scores: hard to explain, and starvation remains
  possible at the extremes.
- Fibonacci numbers as the size score (21, 13, 8, 5, 3, 2, 1, 0): the
  largest drops fall at small sizes, so growing from 100 to 200 lines costs
  8 points while shrinking from 1300 to 800 gains 1.
- Finer buckets at small sizes, such as Fibonacci times 10 or limits at 10,
  50, 100, and 250 lines: rewards shrinking changes that are already easy
  to review.
- A time score of the largest Fibonacci number not above the working days
  waited: it peaks at 5 before an 8-day deadline, so size decides nearly
  every comparison; a pull request under 1300 lines waiting 7 days ranks
  below a fresh one under 300 lines.
- A limit of 5 working days: near the average review time, it would put
  most pull requests in the overdue tier.
- Whole working days: step boundaries depend on the time of day a pull
  request became ready, and limits not divisible by 8 need rounding.
- Office hours: need hours and a time zone per team, and a pull request
  opened in the evening gains nothing overnight.
- Direct requests only by default: misses most requests the review workflow
  makes.
- Size without ignored files, or patterns without defaults: lock files would
  dominate the size of dependency updates, and the per-file data needed to
  exclude them is available.
- Reading only `gh auth token`, or calling `gh api`: makes `gh` a requirement
  of a tool that should need only uv, and `gh api` starts a process per
  query.
- Fetching only as many pull requests as are shown: search does not return
  them in queue order, so the top of the queue could be missing.
- Owner filters as `org:` or `user:` search qualifiers: the qualifier differs
  by owner kind, exclusion needs negated qualifiers, and review queues are
  small enough to filter after the search.

## Revisit when

- The average review time nears or passes the limit.
- The team's experience of review quality by size changes.
- The review workflow changes how or from whom it requests reviews.
- Reviewers work in regions with different weekends.
- GitHub adds a flag for generated files, or changes how search matches
  review requests.
