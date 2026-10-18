from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lca_data_interface import CommonsServer
from lca_data_interface.errors import MissingField, NotOnServer
from tests.stub import StubServer

GROUP = "Test_Group"
NAME = "Test_Repo"
NEWEST = "c0ffee0123456789abcdef0123456789abcdef01"
MIDDLE = "c0ffee0123456789abcdef0123456789abcdef02"
OLDEST = "c0ffee0123456789abcdef0123456789abcdef03"
ABSENT = "0" * 40
ARCHIVE = b"PK-invented-repository-archive"
SERVED_NAME = f"{GROUP}-{NAME}.zip"
HISTORY_PATH = f"/ws/public/history/{GROUP}/{NAME}"
PREPARE_PATH = f"/ws/public/download/json/prepare/{GROUP}/{NAME}"
JSON_TYPE = {"Content-Type": "application/json"}
TOKEN_TYPE = {"Content-Type": "text/plain;charset=UTF-8"}


def released(version: str, commit: str) -> dict[str, object]:
    """A released commit's `releaseInfo`, carrying the fields the server answers."""
    return {
        "repositoryPath": f"{GROUP}/{NAME}",
        "commitId": commit,
        "label": version,
        "version": version,
        "tags": [],
        "description": "",
        "sourceInfo": "",
        "contactInfo": "",
        "changeLog": "",
        "projectInfo": "",
        "projectFunding": "",
        "appropriateUse": "",
        "dqAssessment": "",
        "citation": "",
        "typeOfData": "",
    }


HISTORY: list[dict[str, object]] = [
    {
        "id": NEWEST,
        "message": "Release 1.2099-02.0",
        "user": "invented-user",
        "timestamp": 1791921525000,
        "parentIds": [MIDDLE],
        "userDisplayName": "Invented User",
        "isReleased": True,
        "releaseInfo": released("1.2099-02.0", NEWEST),
    },
    {
        "id": MIDDLE,
        "message": "Rework the unit table",
        "user": "invented-user",
        "timestamp": 1791921515000,
        "parentIds": [OLDEST],
        "userDisplayName": "Invented User",
        "isReleased": False,
        "releaseInfo": None,
    },
    {
        "id": OLDEST,
        "message": "Release 1.2099-01.0",
        "user": "invented-user",
        "timestamp": 1791921500000,
        "parentIds": [],
        "userDisplayName": "Invented User",
        "isReleased": True,
        "releaseInfo": released("1.2099-01.0", OLDEST),
    },
]


def register_download(stub: StubServer, commit: str) -> None:
    """Answer the prepare call for `commit` and the download it prepares."""
    token = f"repository_{GROUP}@{NAME}@{commit}"
    stub.route("GET", f"{PREPARE_PATH}?commitId={commit}", 200, token.encode(), TOKEN_TYPE)
    stub.route(
        "GET",
        f"/ws/public/download/json/{token}",
        200,
        ARCHIVE,
        {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(ARCHIVE)),
            "Content-Disposition": f"attachment; filename={SERVED_NAME}",
        },
    )


def test_releases_are_the_released_commits_newest_first(stub: StubServer, cache: Path) -> None:
    stub.route("GET", HISTORY_PATH, 200, json.dumps(HISTORY).encode(), JSON_TYPE)
    releases = CommonsServer(stub.base).releases(GROUP, NAME)
    assert [release.version for release in releases] == ["1.2099-02.0", "1.2099-01.0"]
    assert [release.commit for release in releases] == [NEWEST, OLDEST]
    assert [release.released_at for release in releases] == [
        datetime(2026, 10, 13, 19, 58, 45, tzinfo=UTC),
        datetime(2026, 10, 13, 19, 58, 20, tzinfo=UTC),
    ]


def test_a_repository_the_server_lacks_is_not_on_the_server(stub: StubServer, cache: Path) -> None:
    missing = f"{GROUP}/Missing"
    text = f"No repository '{missing}' found"
    stub.route("GET", f"/ws/public/history/{missing}", 404, text.encode())
    with pytest.raises(NotOnServer) as raised:
        CommonsServer(stub.base).releases(GROUP, "Missing")
    assert (raised.value.repository, raised.value.commit, raised.value.detail) == (
        missing,
        None,
        text,
    )


def test_a_history_entry_without_its_version_names_the_call_and_the_field(
    stub: StubServer, cache: Path
) -> None:
    entry = {**HISTORY[0], "releaseInfo": {"repositoryPath": f"{GROUP}/{NAME}"}}
    stub.route("GET", HISTORY_PATH, 200, json.dumps([entry]).encode(), JSON_TYPE)
    with pytest.raises(MissingField) as raised:
        CommonsServer(stub.base).releases(GROUP, NAME)
    assert (raised.value.call, raised.value.field) == (f"GET {HISTORY_PATH}", "releaseInfo.version")


def test_a_download_prepares_then_fetches_into_the_commit_s_directory(
    stub: StubServer, cache: Path
) -> None:
    register_download(stub, NEWEST)
    got = CommonsServer(stub.base).download(GROUP, NAME, NEWEST)
    assert got.path == cache / "commons" / "127.0.0.1" / GROUP / NAME / NEWEST / SERVED_NAME
    assert (got.size, got.sha256) == (len(ARCHIVE), hashlib.sha256(ARCHIVE).hexdigest())
    assert stub.requests[0].path == f"{PREPARE_PATH}?commitId={NEWEST}"
    assert stub.requests[1].path == f"/ws/public/download/json/repository_{GROUP}@{NAME}@{NEWEST}"


def test_a_second_download_of_a_commit_makes_no_request(stub: StubServer, cache: Path) -> None:
    register_download(stub, NEWEST)
    server = CommonsServer(stub.base)
    first = server.download(GROUP, NAME, NEWEST)
    served = len(stub.requests)
    assert server.download(GROUP, NAME, NEWEST) == first
    assert len(stub.requests) == served


def test_a_commit_the_server_lacks_is_not_replaced_by_another(
    stub: StubServer, cache: Path
) -> None:
    register_download(stub, NEWEST)
    text = f"commit {ABSENT} not found"
    stub.route("GET", f"{PREPARE_PATH}?commitId={ABSENT}", 404, text.encode())
    with pytest.raises(NotOnServer) as raised:
        CommonsServer(stub.base).download(GROUP, NAME, ABSENT)
    assert (raised.value.repository, raised.value.commit, raised.value.detail) == (
        f"{GROUP}/{NAME}",
        ABSENT,
        text,
    )
    assert [request.path for request in stub.requests] == [f"{PREPARE_PATH}?commitId={ABSENT}"]
