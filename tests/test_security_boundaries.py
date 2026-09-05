from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RENDERING_FILES = [
    PROJECT_ROOT / "react-ui" / "src" / "pages" / "DesignerDetail.jsx",
    PROJECT_ROOT / "react-ui" / "src" / "pages" / "CollectionDetail.jsx",
    PROJECT_ROOT / "react-ui" / "src" / "pages" / "ModerationQueue.jsx",
    PROJECT_ROOT / "web" / "designer.js",
    PROJECT_ROOT / "web" / "collection.js",
]


def test_user_content_renderers_do_not_use_raw_html_sinks():
    forbidden_sinks = (
        "dangerouslySetInnerHTML",
        ".innerHTML",
        ".outerHTML",
        "insertAdjacentHTML",
        "document.write",
    )

    for path in RENDERING_FILES:
        source = path.read_text(encoding="utf-8")
        for sink in forbidden_sinks:
            assert sink not in source, f"{path.name} contains unsafe sink {sink}"


def test_external_links_opened_in_new_tabs_are_isolated():
    import re

    react_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RENDERING_FILES
        if path.suffix == ".jsx"
    )
    vanilla_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RENDERING_FILES
        if path.suffix == ".js"
    )

    react_anchor_tags = re.findall(
        r"<a\b[^>]*\btarget\s*=\s*['\"]_blank['\"][^>]*>",
        react_sources,
    )
    for tag in react_anchor_tags:
        assert re.search(r"\brel\s*=\s*['\"][^'\"]*\bnoreferrer\b", tag)

    assert len(re.findall(r"\.target\s*=\s*['\"]_blank['\"]", vanilla_sources)) == len(
        re.findall(r"\.rel\s*=\s*['\"]noopener\s+noreferrer['\"]", vanilla_sources)
    )
