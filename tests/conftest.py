"""Fixtures shared by the client's tests: the stub server and a cache under the test's directory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.stub import StubServer


@pytest.fixture
def stub() -> Iterator[StubServer]:
    server = StubServer()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "cache"
    monkeypatch.setenv("LCA_DATA_INTERFACE_CACHE", str(directory))
    return directory
