from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def masks_canonical_archive(compose_text):
    # Cover short-form source:/app/data mounts, including an optional :ro/:rw
    # suffix, and long-form mounts whose target is quoted or unquoted.
    return ":/app/data" in compose_text or bool(re.search(
        r"^\s*target:\s*['\"]?/app/data['\"]?\s*(?:#.*)?$",
        compose_text,
        flags=re.MULTILINE,
    ))


def test_api_does_not_mask_image_canonical_archive_with_a_legacy_volume():
    compose_text = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert not masks_canonical_archive(compose_text)
    assert "archive-data:" not in compose_text


def test_canonical_archive_mount_guard_covers_compose_volume_syntaxes():
    assert masks_canonical_archive("- archive-data:/app/data")
    assert masks_canonical_archive("- archive-data:/app/data:ro")
    assert masks_canonical_archive("  target: /app/data")
    assert masks_canonical_archive('  target: "/app/data" # canonical data')
