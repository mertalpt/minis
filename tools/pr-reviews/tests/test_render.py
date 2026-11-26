import re
from datetime import UTC, datetime, timedelta

from pr_reviews import karma, ranking, render
from pr_reviews.ranking import PullRequest, Request

NOW = datetime(2026, 11, 24, tzinfo=UTC)
ESCAPES = re.compile(r"\x1b]8;;[^\x1b]*\x1b\\|\x1b\[[0-9;]*m")


def queue() -> list[ranking.Ranked]:
    prs = [
        PullRequest(
            owner="acme",
            repo=repo,
            number=number,
            title="A title long enough to need truncating on a narrow terminal",
            url=f"https://github.com/acme/{repo}/pull/{number}",
            ready_at=ready_at,
            additions=10,
            deletions=0,
            files=(),
            approved=number == 1,
            request=Request.DIRECT,
        )
        for repo, number, ready_at in [
            ("app", 1, NOW - timedelta(hours=1)),
            ("a-much-longer-name", 12345, NOW - timedelta(weeks=4)),
        ]
    ]
    return ranking.rank(
        prs, now=NOW, tz=UTC, limit_days=8, ignore=[], ignore_by_repo={}
    )


def test_styling_does_not_change_the_layout() -> None:
    styled = render.to_table(queue(), width=None, links=True, color=True)
    plain = render.to_table(queue(), width=None, links=False, color=False)
    assert styled != plain
    assert ESCAPES.sub("", styled) == plain


def test_rows_fit_the_width() -> None:
    lines = render.to_table(queue(), width=90, links=False, color=False).splitlines()
    assert all(len(line) <= 90 for line in lines)
    assert any(line.endswith("...") for line in lines)
    for r in queue():
        [n] = [n for n, line in enumerate(lines) if r.pr.ref in line]
        assert lines[n + 1].strip() == r.pr.url


def test_karma_list_shows_every_counted_pull_request() -> None:
    works = [
        karma.Work(
            "acme",
            "app",
            n,
            f"https://github.com/acme/app/pull/{n}",
            NOW - timedelta(hours=n),
            10 * n,
            0,
            (),
        )
        for n in (1, 22, 333)
    ]
    result = karma.compute(
        works,
        [],
        now=NOW,
        tz=UTC,
        window=karma.Window(2, 10),
        include_owners=[],
        exclude_owners=[],
        ignore=[],
        ignore_by_repo={},
    )
    lines = render.karma_list(result, color=False).splitlines()
    assert lines[0] == "Reviewed (3)"
    assert lines[-1] == "Authored (0)"
    rows = [line for line in lines if "/pull/" in line]
    assert [row.split()[0] for row in rows] == ["10", "220", "3330"]
    assert len({row.index("https://") for row in rows}) == 1
