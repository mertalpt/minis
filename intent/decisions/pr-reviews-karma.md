# PR review karma

Facing people who cannot easily see whether they give back as much review as
they ask for, we show each user the ratio of the lines they recently reviewed
to the lines they recently authored, weighted toward newer work, rather than
counts of reviews or a figure for a team, to let people check and adjust
their own balance, accepting a best-effort figure that one large pull request
can swing.

## Governs

- `tools/pr-reviews/**`

## Context

- Karma is for checking your own balance, not for policing others, and part
  of its appeal is that it is fun.
- When a pull request needs several approvals, reviewing has to outweigh
  authoring for the team's work to flow: with 2 required approvals, a
  balanced person reviews about twice the lines they author.
- What is balanced depends on the person, for example on their seniority.
- Karma shares the `pr-reviews` tool with the queue, and with it the
  credentials, the configuration file, the owner filters, the ignore
  patterns, and the measurement of working days set in
  [PR review queue](pr-reviews-queue.md).
- GraphQL `contributionsCollection` returned none of a user's reviews in
  private repositories while search found hundreds, and returns one entry
  per pull request without a consistent choice of which review it dates.
- GraphQL search matches `reviewed-by:@me` and `author:@me`, and cannot
  filter by review date. `PullRequest.reviews(author:)` lists a user's
  reviews oldest first, with their state and submission time; a pending
  review has no submission time.
- Replying in a review thread creates a `COMMENTED` review, which
  `reviewed-by:` matches, including on the user's own pull requests.
- GitHub records the commit each review was made on, but sizing the pull
  request at that commit costs further queries.
- The tool is low-stakes and best effort: it serves the common case, and
  known gaps are documented rather than handled.

## Decision

- `pr-reviews karma` reports the current karma of the user running it.
- Reviewed work is each pull request by someone else on which the user
  submitted at least one review, in any state, found by searching
  `is:pr reviewed-by:@me -author:@me`. It counts once, dated at the user's
  first submitted review.
- Authored work is each pull request the user opened that is not currently a
  draft, open, merged or closed without merging, found by searching
  `is:pr author:@me draft:false`. It is dated at the latest time it was
  marked ready for review, or at its creation if it never was a draft.
- Both searches add `updated:>=` an instant at or before the start of the
  window, so they return a superset of the work in the window; ages are
  computed from the dates above.
- A pull request's lines are its additions plus deletions as GitHub reports
  them when the tool runs, excluding files that match the queue's ignore
  patterns.
- Age is working time since the date, measured as the queue's wait.
- With a full-weight period F, 2 working days by default, and a window N, 10
  working days by default, work aged F or less weighs 1, work aged between F
  and N weighs `1 - ((age - F) / (N - F))^2`, and work aged N or more is not
  counted. F must be less than N after flags override the configuration.
- Karma is the sum of weight times lines over reviewed work divided by the
  same sum over authored work. When the authored sum is 0, the tool says no
  authored work falls in the window instead of giving a figure.
- An optional target, set in the configuration or by a flag, is shown
  beside the figure. The tool encodes no seniority or role.
- Every repository the credentials can read counts, narrowed by the queue's
  owner filters.
- The settings that only karma uses live in a `[karma]` table of the
  configuration file.

## Consequences

- Each user sets and reads their own target.
- A pull request that grows after the user's review counts its new size.
- A comment review counts as fully as an approval.
- Authored work counts whether or not anyone reviewed it, so a repository the
  user works in alone lowers karma unless an owner filter excludes it.
- The figure changes day by day as work ages, and returns to no figure when
  no authored work remains in the window.
- Each run costs one search per side, plus one query per further 100 files
  of a pull request with more than 100 changed files.

## Alternatives

- GraphQL `contributionsCollection`: it misses reviews in private
  repositories and dates each pull request by an unpredictable review.
- Crediting each review separately: replies in review threads create comment
  reviews, which would inflate the figure.
- Sizing a pull request at the commit of the user's first review: more
  accurate, but costs a query per review for little gain in a best-effort
  figure.
- Counting only authored work that others reviewed: it delays authored work
  until reviews arrive and ties the figure to others' behavior; owner filters
  exclude solo repositories instead.
- Including the reviews the user's work received, or its waiting time: it
  brings other people's behavior into a figure meant to show the user's own.
- Karma for other people or whole teams, or comparisons between people: the
  figure is for checking yourself, not for policing others.
- Encoding seniority or role in the figure or a default target: people set
  their own target instead.
- History or trends of karma over time: the tool reports the current figure.

## Revisit when

- The number of required approvals changes how the team reads karma.
- GitHub search can filter by review date, or `contributionsCollection`
  covers private repositories reliably.
- Comment reviews from thread replies become distinguishable from review
  submissions.
