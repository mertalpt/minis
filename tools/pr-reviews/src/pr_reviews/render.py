"""Output formats for the ranked queue and karma."""

import json
from collections.abc import Sequence
from typing import Any

from pr_reviews.karma import Karma, Side
from pr_reviews.ranking import WORKING_DAY, Ranked

HEADERS = ("SCORE", "SIZE", "WAITED", "REQUEST", "PR")
INDENT = "  "
GAP = "  "
MIN_TITLE = 20
APPROVED_MARK = " (+)"
BOLD = "1"
DIM = "2"
GREEN = "32"
RED = "1;31"


def to_json(queue: Sequence[Ranked]) -> str:
    """Return the queue as a JSON array in ranked order."""
    return json.dumps(
        [
            {
                "rank": i,
                "overdue": r.overdue,
                "priority": r.priority,
                "size_score": r.size_score,
                "time_score": r.time_score,
                "size": r.size,
                "size_bucket": r.size_bucket,
                "wait_days": round(r.wait / WORKING_DAY, 3),
                "waiting_since": r.pr.ready_at.isoformat(),
                "ref": r.pr.ref,
                "owner": r.pr.owner,
                "repo": r.pr.repo,
                "number": r.pr.number,
                "title": r.pr.title,
                "url": r.pr.url,
                "request": r.pr.request.value,
                "approved": r.pr.approved,
            }
            for i, r in enumerate(queue, start=1)
        ],
        indent=2,
    )


def to_table(
    queue: Sequence[Ranked],
    *,
    hidden: int = 0,
    width: int | None,
    links: bool,
    color: bool,
) -> str:
    """Return the queue as a table in ranked order.

    Overdue pull requests and the rest are listed in separate sections. Each
    pull request takes two lines: its scores, request, reference, and title,
    then its URL.

    Args:
        queue: The ranked pull requests to show.
        hidden: How many lower-ranked pull requests are not shown.
        width: The columns to fit titles into, or None to keep them whole.
        links: Whether to make each PR reference a terminal hyperlink.
        color: Whether to style the output with ANSI escape codes.

    Returns:
        The table, or a note that the queue is empty.
    """
    if not queue:
        return "No pull requests are waiting for your review."
    rows = [
        (
            str(r.priority),
            str(r.size),
            f"{r.wait / WORKING_DAY:.1f}d",
            r.pr.request.value + (APPROVED_MARK if r.pr.approved else ""),
            r.pr.ref,
        )
        for r in queue
    ]
    widths = [max(len(row[i]) for row in [HEADERS, *rows]) for i in range(len(HEADERS))]
    title_start = len(INDENT) + sum(w + len(GAP) for w in widths)
    title_width = None if width is None else max(MIN_TITLE, width - title_start)
    url_indent = " " * (len(INDENT) + widths[0] + len(GAP))

    def pad(cells: Sequence[str]) -> list[str]:
        return [cell.ljust(w) for cell, w in zip(cells, widths, strict=True)]

    header = INDENT + _style(GAP.join([*pad(HEADERS), "TITLE"]), BOLD, color)
    lines = []
    sections = [
        ("Overdue", RED, [n for n, r in enumerate(queue) if r.overdue]),
        ("Queue", BOLD, [n for n, r in enumerate(queue) if not r.overdue]),
    ]
    for name, heading_style, members in sections:
        if not members:
            continue
        lines += [_style(f"{name} ({len(members)})", heading_style, color), header]
        for n in members:
            pr = queue[n].pr
            cells = pad(rows[n])
            if pr.approved:
                mark = _style(APPROVED_MARK, GREEN, color)
                cells[-2] = cells[-2].replace(APPROVED_MARK, mark, 1)
            if links:
                # Padding stays outside the link so the escape codes, which
                # take no columns, do not break alignment.
                cells[-1] = _hyperlink(pr.ref, pr.url) + cells[-1][len(pr.ref) :]
            title = pr.title
            if title_width is not None:
                title = _truncate(title, title_width)
            lines.append(INDENT + GAP.join([*cells, title]))
            lines.append(url_indent + _style(pr.url, DIM, color))
    if hidden:
        lines.append(f"... and {hidden} more; --top 0 shows all.")
    return "\n".join(lines)


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 3, 0)] + "..."


def _style(text: str, sgr: str, color: bool) -> str:
    return f"\033[{sgr}m{text}\033[0m" if color else text


def _hyperlink(text: str, url: str) -> str:
    # OSC 8; terminals without support show the text alone.
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def karma_to_json(karma: Karma, target: float | None) -> str:
    """Return the karma and its counted pull requests as a JSON object."""
    value = karma.value

    def side(s: Side) -> dict[str, Any]:
        return {
            "weighted_lines": round(s.weighted_lines, 1),
            "prs": len(s.counted),
            "pull_requests": [
                {
                    "ref": c.work.ref,
                    "url": c.work.url,
                    "lines": c.lines,
                    "date": c.work.dated_at.isoformat(),
                    "age_days": round(c.age / WORKING_DAY, 3),
                    "weight": round(c.weight, 3),
                }
                for c in s.counted
            ],
        }

    return json.dumps(
        {
            "karma": None if value is None else round(value, 3),
            "target": target,
            "window_days": karma.window.days,
            "full_weight_days": karma.window.full_days,
            "reviewed": side(karma.reviewed),
            "authored": side(karma.authored),
        },
        indent=2,
    )


def karma_to_text(karma: Karma, target: float | None, *, color: bool) -> str:
    """Return the karma as a short summary.

    Args:
        karma: The karma to show.
        target: The user's target, or None.
        color: Whether to style the output with ANSI escape codes.

    Returns:
        The summary.
    """
    value = karma.value
    figure = "-" if value is None else f"{value:.2f}"
    if target is not None:
        figure += f"  (target {target:g})"
    if value is None:
        figure += "  no authored work in the window"
    rows = [("Karma", _style(figure, BOLD, color))]
    for name, s in (("Reviewed", karma.reviewed), ("Authored", karma.authored)):
        n = len(s.counted)
        rows.append(
            (name, f"{s.weighted_lines:.0f} lines in {n} PR{'' if n == 1 else 's'}")
        )
    w = karma.window
    rows.append(("Window", f"{w.days:g} working days, full weight for {w.full_days:g}"))
    label = max(len(name) for name, _ in rows)
    return "\n".join(f"{name.ljust(label)}  {text}" for name, text in rows)


KARMA_HEADERS = ("LINES", "WEIGHT", "AGE", "DATED", "URL")


def karma_list(karma: Karma, *, color: bool) -> str:
    """Return the counted pull requests of each side as a table, newest first.

    Dates are in the machine's local time zone.
    """
    lines = []
    for name, s in (("Reviewed", karma.reviewed), ("Authored", karma.authored)):
        lines.append(_style(f"{name} ({len(s.counted)})", BOLD, color))
        if not s.counted:
            continue
        rows = [
            (
                str(c.lines),
                f"{c.weight:.2f}",
                f"{c.age / WORKING_DAY:.1f}d",
                c.work.dated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                c.work.url,
            )
            for c in s.counted
        ]
        widths = [max(len(r[i]) for r in [KARMA_HEADERS, *rows]) for i in range(4)]
        lines.append(_style(_karma_row(KARMA_HEADERS, widths), BOLD, color))
        lines += [_karma_row(r, widths) for r in rows]
    return "\n".join(lines)


def _karma_row(cells: Sequence[str], widths: Sequence[int]) -> str:
    # Lines and weight align right; the URL, last, needs no padding.
    padded = [
        cell.rjust(w) if i < 2 else cell.ljust(w)
        for i, (cell, w) in enumerate(zip(cells, widths, strict=False))
    ]
    return INDENT + GAP.join([*padded, cells[-1]])
