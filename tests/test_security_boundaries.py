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

    assert react_sources.count('target="_blank"') == react_sources.count(
        'rel="noreferrer"'
    )
    assert vanilla_sources.count('target = "_blank"') == vanilla_sources.count(
        'rel = "noopener noreferrer"'
    )
