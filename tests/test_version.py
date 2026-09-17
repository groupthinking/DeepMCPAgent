from importlib.metadata import version as installed_version
from pathlib import Path

from deepmcpagent.version import __version__

PROJECT_ROOT = Path(__file__).parents[1]


def test_version_matches_package_metadata_and_documented_release() -> None:
    changelog = (PROJECT_ROOT / "docs" / "changelog.md").read_text(encoding="utf-8")
    release_heading = next(
        line.removeprefix("## ") for line in changelog.splitlines() if line.startswith("## ")
    )

    assert installed_version("deepmcpagent") == __version__ == release_heading
