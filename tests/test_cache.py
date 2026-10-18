from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lca_data_interface import __version__
from lca_data_interface.cache import cache_dir, cached, fetch
from lca_data_interface.errors import MissingField, ServiceError, ShortDownload
from lca_data_interface.transport import ensure_ok, new_session, send
from tests.stub import StubServer


def test_the_cache_is_the_directory_the_variable_names(cache: Path) -> None:
    assert cache_dir() == cache


def test_a_download_lands_under_its_served_name_with_its_hash(
    stub: StubServer, cache: Path
) -> None:
    stub.route(
        "GET",
        "/f",
        200,
        b"hello",
        {
            "Content-Length": "5",
            "Content-Disposition": "attachment; filename=BAFU-2026 v1_ecoSpold v1.zip",
        },
    )
    got = fetch(new_session(), stub.base + "/f", cache / "d", call="GET /f")
    assert got.path == cache / "d" / "BAFU-2026 v1_ecoSpold v1.zip"
    assert got.size == 5 and got.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert (
        cache / "d" / "sha256.txt"
    ).read_text() == f"{got.sha256}  BAFU-2026 v1_ecoSpold v1.zip\n"
    assert not list((cache / "d").glob("*.part"))


def test_a_cached_file_is_returned_and_a_changed_one_is_not(stub: StubServer, cache: Path) -> None:
    stub.route(
        "GET",
        "/f",
        200,
        b"hello",
        {"Content-Length": "5", "Content-Disposition": "attachment; filename=a.zip"},
    )
    directory = cache / "d"
    got = fetch(new_session(), stub.base + "/f", directory, call="GET /f")
    assert cached(directory) == got
    (directory / "a.zip").write_bytes(b"HELLO")
    assert cached(directory) is None


def test_a_body_shorter_than_its_length_leaves_nothing_under_the_final_name(
    stub: StubServer, cache: Path
) -> None:
    stub.route(
        "GET",
        "/f",
        200,
        b"hel",
        {"Content-Length": "5", "Content-Disposition": "attachment; filename=a.zip"},
    )
    with pytest.raises(ShortDownload) as raised:
        fetch(new_session(), stub.base + "/f", cache / "d", call="GET /f")
    assert (raised.value.expected, raised.value.received) == (5, 3)
    assert not (cache / "d" / "a.zip").exists() and not (cache / "d" / "sha256.txt").exists()


def test_a_served_name_that_is_a_path_is_refused(stub: StubServer, cache: Path) -> None:
    for path, name in (("/a", "../x.zip"), ("/b", "a/b.zip")):
        stub.route(
            "GET",
            path,
            200,
            b"hello",
            {
                "Content-Length": "5",
                "Content-Disposition": f"attachment; filename={name}",
            },
        )
        with pytest.raises(ServiceError) as raised:
            fetch(new_session(), stub.base + path, cache / "d", call="GET /f")
        assert "Content-Disposition" in str(raised.value)
    assert not (cache / "d").exists() and not (cache / "x.zip").exists()


def test_a_response_without_a_served_name_names_the_header(stub: StubServer, cache: Path) -> None:
    stub.route("GET", "/f", 200, b"hello", {"Content-Length": "5"})
    with pytest.raises(MissingField) as raised:
        fetch(new_session(), stub.base + "/f", cache / "d", call="GET /f")
    assert (raised.value.call, raised.value.field) == ("GET /f", "Content-Disposition")
    assert not (cache / "d").exists()


def test_a_refused_status_names_the_call_and_the_status(stub: StubServer) -> None:
    stub.route("GET", "/x", 500, b"boom")
    response = send(new_session(), "GET", stub.base + "/x", call="GET /x")
    with pytest.raises(ServiceError) as raised:
        ensure_ok(response, call="GET /x")
    assert (raised.value.call, raised.value.status) == ("GET /x", 500)
    assert "boom" in raised.value.detail


def test_an_unreachable_host_is_a_service_error_naming_the_call() -> None:
    with pytest.raises(ServiceError) as raised:
        send(new_session(), "GET", "http://127.0.0.1:9/nothing", call="GET /nothing")
    assert (raised.value.call, raised.value.status) == ("GET /nothing", None)


def test_every_request_carries_the_package_s_user_agent(stub: StubServer) -> None:
    stub.route("GET", "/f", 200, b"hello")
    send(new_session(), "GET", stub.base + "/f", call="GET /f")
    assert stub.requests[0].headers["User-Agent"] == f"lca-data-interface/{__version__}"
