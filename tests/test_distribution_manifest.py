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
