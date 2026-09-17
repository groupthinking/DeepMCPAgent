from importlib.metadata import version as installed_version
from pathlib import Path

from deepmcpagent.version import __version__

PROJECT_ROOT = Path(__file__).parents[1]


def test_version_matches_package_metadata_and_documented_release() -> None:
    changelog_paths = (PROJECT_ROOT / "CHANGELOG.md", PROJECT_ROOT / "docs" / "changelog.md")
    release_headings = [
        next(
            line.removeprefix("## ")
            for line in changelog_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        )
        for changelog_path in changelog_paths
    ]

    assert (
        installed_version("deepmcpagent")
        == __version__
        == release_headings[0]
        == release_headings[1]
    )
