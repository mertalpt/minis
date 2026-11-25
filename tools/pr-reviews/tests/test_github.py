import email.message
import io
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import pytest

from pr_reviews import cli, github
from pr_reviews.ranking import ChangedFile, Request

TOKEN = "ghp_secretvalue"


def pr_node(number: int, **overrides: Any) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": f"PR_{number}",
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/acme/app/pull/{number}",
        "createdAt": "2026-11-02T09:00:00Z",
        "additions": 30,
        "deletions": 5,
        "reviewDecision": None,
        "repository": {"name": "app", "owner": {"login": "acme"}},
        "timelineItems": {"nodes": []},
        "files": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [{"path": "a.py", "additions": 30, "deletions": 5}],
        },
    }
    node.update(overrides)
    return node


def page(nodes: list[Any], cursor: str | None = None) -> dict[str, Any]:
    return {
        "data": {
            "search": {
                "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                "nodes": nodes,
            }
        }
    }


class FakeGitHub:
    """Answers the client's queries from canned responses."""

    def __init__(self, responses: dict[tuple[str, str | None], dict[str, Any]]):
        self.responses = responses

    def __call__(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if query == github.FILES_QUERY:
            key = (variables["id"], variables["after"])
        else:
            key = (variables["q"], variables["after"])
        return self.responses[key]


def test_review_requests() -> None:
    first_files = {
        "pageInfo": {"hasNextPage": True, "endCursor": "f1"},
        "nodes": [{"path": "a.py", "additions": 1, "deletions": 0}],
    }
    fake = FakeGitHub(
        {
            (github.SEARCH_DIRECT, None): page([{"id": "PR_2"}]),
            (github.SEARCH_ALL, None): page(
                [
                    pr_node(
                        1,
                        timelineItems={
                            "nodes": [{"createdAt": "2026-11-20T10:00:00Z"}]
                        },
                        files=first_files,
                    ),
                    {},
                    None,
                ],
                cursor="s1",
            ),
            (github.SEARCH_ALL, "s1"): page([pr_node(2, reviewDecision="APPROVED")]),
            ("PR_1", "f1"): {
                "data": {
                    "node": {
                        "files": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {"path": "uv.lock", "additions": 9, "deletions": 9}
                            ],
                        }
                    }
                }
            },
        }
    )

    one, two = github.Client(fake).review_requests()

    assert (one.request, two.request) == (Request.TEAM, Request.DIRECT)
    assert (one.approved, two.approved) == (False, True)
    assert one.ready_at == datetime(2026, 11, 20, 10, tzinfo=UTC)
    assert two.ready_at == datetime(2026, 11, 2, 9, tzinfo=UTC)
    assert one.files == (ChangedFile("a.py", 1, 0), ChangedFile("uv.lock", 9, 9))
    assert one.ref == "acme/app#1"


def test_errors_without_data_fail() -> None:
    def fake(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        return {"data": None, "errors": [{"message": "Something went wrong"}]}

    with pytest.raises(github.GitHubError, match="Something went wrong"):
        github.Client(fake).review_requests()


def test_partial_data_warns() -> None:
    def fake(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = page([None])
        response["errors"] = [{"message": "protected by SAML"}]
        return response

    client = github.Client(fake)
    assert client.review_requests() == []
    assert client.warnings == ["protected by SAML"]


def test_missing_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert cli.main(["queue"]) == 1
    assert "no GitHub credentials" in capsys.readouterr().err


def test_rejected_credentials_do_not_print_the_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    sent: list[Any] = []

    def urlopen(request: Any, timeout: float) -> Any:
        sent.append(request)
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            email.message.Message(),
            io.BytesIO(b"{}"),
        )

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    assert cli.main(["queue"]) == 1
    out = capsys.readouterr()
    assert "rejected the credentials" in out.err
    assert TOKEN not in out.out + out.err
    [request] = sent
    assert request.full_url == "https://api.github.com/graphql"
    assert request.get_header("Authorization") == f"bearer {TOKEN}"
    assert json.loads(request.data)["variables"]["q"] == github.SEARCH_DIRECT


def test_queue_shows_the_top_requests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    fake = FakeGitHub(
        {
            (github.SEARCH_DIRECT, None): page([]),
            (github.SEARCH_ALL, None): page([pr_node(n) for n in range(1, 26)]),
        }
    )
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(github, "http_transport", lambda token: fake)

    assert cli.main(["queue"]) == 0
    out = capsys.readouterr().out
    assert out.count("https://github.com/acme/app/pull/") == 20
    assert "5 more" in out

    assert cli.main(["queue", "--top", "0", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 25
