"""Output formats for the ranked queue."""

import json
from collections.abc import Sequence

from pr_reviews.ranking import WORKING_DAY, Ranked

HEADERS = ("SCORE", "SIZE", "BUCKET", "WAITED", "REQUEST", "PR")
INDENT = "  "
GAP = "  "
MIN_TITLE = 20
APPROVED_MARK = "  approved"
BOLD = "1"
DIM = "2"
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
    queue: Sequence[Ranked], *, width: int | None, links: bool, color: bool
) -> str:
    """Return the queue as a table in ranked order.

    Overdue pull requests and the rest are listed in separate sections. Each
    pull request takes two lines: its scores, reference, and title, then its
    URL.

    Args:
        queue: The ranked pull requests.
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
            r.size_bucket,
            f"{r.wait / WORKING_DAY:.1f}d",
            r.pr.request.value,
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
            if links:
                # Padding stays outside the link so the escape codes, which
                # take no columns, do not break alignment.
                cells[-1] = _hyperlink(pr.ref, pr.url) + cells[-1][len(pr.ref) :]
            mark = APPROVED_MARK if pr.approved else ""
            title = pr.title
            if title_width is not None:
                title = _truncate(title, title_width - len(mark))
            line = INDENT + GAP.join([*cells, title + mark])
            lines.append(_style(line, DIM, color) if pr.approved else line)
            lines.append(url_indent + _style(pr.url, DIM, color))
    return "\n".join(lines)


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 3, 0)] + "..."


def _style(text: str, sgr: str, color: bool) -> str:
    return f"\033[{sgr}m{text}\033[0m" if color else text


def _hyperlink(text: str, url: str) -> str:
    # OSC 8; terminals without support show the text alone.
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
