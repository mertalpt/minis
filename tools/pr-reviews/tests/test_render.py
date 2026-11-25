import re
from datetime import UTC, datetime

from pr_reviews import ranking, render
from pr_reviews.ranking import PullRequest, Request


def queue() -> list[ranking.Ranked]:
    prs = [
        PullRequest(
            owner="acme",
            repo=repo,
            number=number,
            title="Title",
            url=f"https://github.com/acme/{repo}/pull/{number}",
            ready_at=datetime(2026, 11, 23, tzinfo=UTC),
            additions=10,
            deletions=0,
            files=(),
            approved=number == 1,
            request=Request.DIRECT,
        )
        for repo, number in [("app", 1), ("a-much-longer-name", 12345)]
    ]
    return ranking.rank(
        prs,
        now=datetime(2026, 11, 24, tzinfo=UTC),
        tz=UTC,
        limit_days=8,
        ignore=[],
        ignore_by_repo={},
    )


def test_links_do_not_change_the_layout() -> None:
    linked = render.to_table(queue(), links=True)
    plain = render.to_table(queue(), links=False)
    assert linked != plain
    assert re.sub(r"\x1b]8;;[^\x1b]*\x1b\\", "", linked) == plain
