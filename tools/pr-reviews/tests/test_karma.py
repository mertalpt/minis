from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pr_reviews.karma import Window, WindowError, Work, compute
from pr_reviews.ranking import WORKING_DAY, ChangedFile, working_time

# 2026-11-23 is a Monday.
MONDAY = datetime(2026, 11, 23, tzinfo=UTC)
NOW = MONDAY + timedelta(weeks=3)


def make_work(number: int = 1, **changes: object) -> Work:
    work = Work(
        owner="acme",
        repo="app",
        number=number,
        url=f"https://github.com/acme/app/pull/{number}",
        dated_at=NOW,
        additions=100,
        deletions=0,
        files=(),
    )
    return replace(work, **changes)  # type: ignore[arg-type]


def karma_of(
    reviewed: list[Work], authored: list[Work], **options: object
) -> float | None:
    kwargs: dict[str, object] = {
        "now": NOW,
        "tz": UTC,
        "window": Window(2, 10),
        "include_owners": [],
        "exclude_owners": [],
        "ignore": [],
        "ignore_by_repo": {},
    }
    kwargs.update(options)
    return compute(reviewed, authored, **kwargs).value  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("days", "weight"), [(0, 1), (2, 1), (6, 0.75), (9, 1 - (7 / 8) ** 2), (10, 0)]
)
def test_weight_by_age(days: float, weight: float) -> None:
    assert Window(2, 10).weight(days * WORKING_DAY) == pytest.approx(weight)


@pytest.mark.parametrize(("full", "window"), [(10, 10), (12, 10)])
def test_full_weight_period_must_be_shorter(full: float, window: float) -> None:
    with pytest.raises(WindowError, match="shorter than the window"):
        Window(full, window)


def test_karma_weighs_lines_by_age() -> None:
    # 6 working days back from Monday midnight is Friday midnight 10 days before.
    six_days_ago = NOW - timedelta(days=10)
    reviewed = [make_work(1, additions=300), make_work(2, dated_at=six_days_ago)]
    authored = [make_work(3), make_work(4, dated_at=NOW - timedelta(weeks=3))]
    assert karma_of(reviewed, authored) == pytest.approx((300 + 75) / 100)


def test_no_authored_lines_gives_no_karma() -> None:
    old = make_work(2, dated_at=NOW - timedelta(weeks=3))
    assert karma_of([make_work(1)], [old]) is None


def test_owner_filters_apply_to_both_sides() -> None:
    reviewed = [make_work(1, owner="Acme"), make_work(2, owner="other")]
    authored = [make_work(3, owner="acme"), make_work(4, owner="OTHER", additions=300)]
    assert karma_of(reviewed, authored, include_owners=["ACME"]) == 1
    assert karma_of(reviewed, authored, exclude_owners=["acme"]) == pytest.approx(1 / 3)


def test_ignored_files_do_not_count() -> None:
    reviewed = make_work(
        1,
        additions=1100,
        files=(ChangedFile("uv.lock", 500, 0), ChangedFile("gen/x.py", 500, 0)),
    )
    karma = karma_of(
        [reviewed],
        [make_work(2)],
        ignore=["uv.lock"],
        ignore_by_repo={"ACME/App": ["gen/*"]},
    )
    assert karma == 1


@pytest.mark.parametrize("days", [0.5, 2, 5, 10, 13])
def test_search_starts_before_the_window(days: float) -> None:
    window = Window(0, days)
    for hour in range(0, 7 * 24, 5):
        now = MONDAY + timedelta(hours=hour)
        assert working_time(window.search_since(now), now, None) >= days * WORKING_DAY
