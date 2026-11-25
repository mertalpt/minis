"""Output formats for the ranked queue."""

import json
from collections.abc import Sequence

from pr_reviews.ranking import WORKING_DAY, Ranked

TITLE_WIDTH = 60
HEADERS = (
    "DUE",
    "SCORE",
    "SIZE",
    "BUCKET",
    "WAITED",
    "REQUEST",
    "APPROVED",
    "PR",
    "TITLE",
    "URL",
)


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


def to_table(queue: Sequence[Ranked], *, links: bool) -> str:
    """Return the queue as a table in ranked order.

    Args:
        queue: The ranked pull requests.
        links: Whether to make each PR reference a terminal hyperlink.

    Returns:
        The table, or a note that the queue is empty.
    """
    if not queue:
        return "No pull requests are waiting for your review."
    rows = [
        (
            "OVERDUE" if r.overdue else "",
            str(r.priority),
            str(r.size),
            r.size_bucket,
            f"{r.wait / WORKING_DAY:.1f}d",
            r.pr.request.value,
            "approved" if r.pr.approved else "",
            r.pr.ref,
            _truncate(r.pr.title, TITLE_WIDTH),
            r.pr.url,
        )
        for r in queue
    ]
    widths = [max(len(row[i]) for row in [HEADERS, *rows]) for i in range(len(HEADERS))]
    ref_column = HEADERS.index("PR")
    lines = []
    for n, row in enumerate([HEADERS, *rows]):
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=True)]
        if links and n > 0:
            # Padding stays outside the link so the escape codes, which take
            # no columns, do not break alignment.
            ref = row[ref_column]
            url = queue[n - 1].pr.url
            cells[ref_column] = _hyperlink(ref, url) + cells[ref_column][len(ref) :]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def _hyperlink(text: str, url: str) -> str:
    # OSC 8; terminals without support show the text alone.
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
