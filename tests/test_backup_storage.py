import json

import pytest

from scripts.backup_storage import upload_backup


class FakeStorage:
    def __init__(self):
        self.uploads = []
        self.metadata = None
        self.size = None

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.uploads.append((filename, bucket, key, ExtraArgs))
        if key.endswith(".sql.enc"):
            self.size = __import__("pathlib").Path(filename).stat().st_size
            self.metadata = ExtraArgs["Metadata"]

    def head_object(self, Bucket, Key):
        return {"ContentLength": self.size, "Metadata": self.metadata}


def test_uploads_only_encrypted_artifact_and_manifest_then_verifies(tmp_path):
    backup = tmp_path / "trainspotting-20260905.sql.enc"
    backup.write_bytes(b"ciphertext-only")
    manifest = {
        "format_version": 1,
        "encrypted_sha256": "abc123",
        "encrypted_bytes": len(backup.read_bytes()),
    }
    backup.with_suffix(backup.suffix + ".json").write_text(json.dumps(manifest))
    storage = FakeStorage()

    result = upload_backup(storage, "private-backups", "staging/mysql", backup)

    assert result["object_key"] == "staging/mysql/trainspotting-20260905.sql.enc"
    assert [upload[2] for upload in storage.uploads] == [
        "staging/mysql/trainspotting-20260905.sql.enc",
        "staging/mysql/trainspotting-20260905.sql.enc.json",
    ]
    assert storage.uploads[0][3]["Metadata"]["encrypted-sha256"] == "abc123"


def test_upload_fails_when_remote_verification_disagrees(tmp_path):
    backup = tmp_path / "backup.sql.enc"
    backup.write_bytes(b"ciphertext")
    backup.with_suffix(backup.suffix + ".json").write_text(
        json.dumps({"format_version": 1, "encrypted_sha256": "expected"})
    )
    storage = FakeStorage()

    def wrong_head(**_kwargs):
        return {"ContentLength": 1, "Metadata": {"encrypted-sha256": "wrong"}}

    storage.head_object = wrong_head
    with pytest.raises(RuntimeError, match="size verification"):
        upload_backup(storage, "bucket", "", backup)
