from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_api_does_not_mask_image_canonical_archive_with_a_legacy_volume():
    configuration = yaml.safe_load(
        (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    )

    api_volumes = configuration["services"]["api"].get("volumes", [])

    assert all(
        not str(volume).endswith(":/app/data") for volume in api_volumes
    )
    assert "archive-data" not in configuration.get("volumes", {})
