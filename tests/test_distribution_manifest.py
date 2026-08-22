import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT_DOCS = [
    REPO / "README.md",
    REPO / "CONTRIBUTING.md",
    REPO / "ROADMAP.md",
    REPO / "LAUNCH_NOTES.md",
]
ROOT_ARTIFACTS = {"SECURITY.md", "CHANGELOG.md", "CITATION.cff"}


def _local_links(path: Path):
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text()):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        yield target.split("#", 1)[0]


def test_packaged_document_links_resolve_in_repository():
    for document in ROOT_DOCS:
        for target in _local_links(document):
            resolved = (document.parent / target).resolve()
            assert resolved.is_relative_to(REPO)
            assert resolved.exists(), f"{document.name} references missing {target}"


def test_manifest_includes_referenced_root_artifacts():
    manifest = (REPO / "MANIFEST.in").read_text().splitlines()
    included = {line.removeprefix("include ") for line in manifest if line.startswith("include ")}
    assert ROOT_ARTIFACTS <= included


def _match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_citation_matches_package_release_metadata():
    pyproject = (REPO / "pyproject.toml").read_text()
    citation = (REPO / "CITATION.cff").read_text()
    changelog = (REPO / "CHANGELOG.md").read_text()

    package_version = _match(r'^version = "([^"]+)"$', pyproject)
    package_author = _match(r'^authors = \[\{name = "([^"]+)"\}\]$', pyproject)
    citation_version = _match(r"^version: (\S+)$", citation)
    citation_date = _match(r"^date-released: (\S+)$", citation)
    citation_affiliation = _match(r"^    affiliation: (.+)$", citation)

    assert citation_version == package_version
    assert f"## {package_version} — {citation_date}" in changelog
    assert citation_affiliation == package_author == "Amazed Labs"
