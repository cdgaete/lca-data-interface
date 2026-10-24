"""The project states Apache-2.0, carries the licence and Carlos Gaete-Morales's notice at its
root, and ships both in the wheel and the sdist."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
APACHE_2_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def test_the_project_states_its_licence() -> None:
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())["project"]
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]


def test_the_licence_and_the_notice_are_at_the_root() -> None:
    licence = (REPOSITORY / "LICENSE").read_bytes()
    # the text served at https://www.apache.org/licenses/LICENSE-2.0.txt, which the core carries
    assert hashlib.sha256(licence).hexdigest() == APACHE_2_SHA256

    notice = (REPOSITORY / "NOTICE").read_text()
    assert notice.startswith("lca-data-interface\n")
    assert "Copyright 2026 Carlos Gaete-Morales" in notice
    assert "This product includes software developed by Carlos Gaete-Morales." in notice


def test_the_wheel_and_the_sdist_carry_both(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    built = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(built), str(REPOSITORY)],
        check=True,
        capture_output=True,
    )

    (wheel,) = built.glob("*.whl")
    (sdist,) = built.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()

    for names in (wheel_names, sdist_names):
        found = {name.rsplit("/", 1)[-1] for name in names}
        assert {"LICENSE", "NOTICE"} <= found
