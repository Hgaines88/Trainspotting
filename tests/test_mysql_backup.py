import hashlib
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from scripts import mysql_backup


def test_database_config_decodes_credentials_without_logging_them():
    config = mysql_backup.database_config(
        "mysql+pymysql://archive:p%40ss@mysql.internal:3307/trainspotting"
    )
    assert config == {
        "host": "mysql.internal",
        "port": 3307,
        "user": "archive",
        "password": "p@ss",
        "database": "trainspotting",
    }


def test_encrypted_backup_round_trip_and_tamper_detection(tmp_path, monkeypatch):
    dump = b"-- MySQL dump\nCREATE TABLE `designers` (`id` int);\n"
    monkeypatch.setattr(mysql_backup, "dump_database", lambda _url: dump)
    key = Fernet.generate_key().decode("ascii")
    backup = tmp_path / "trainspotting.sql.enc"

    manifest = mysql_backup.create_backup("mysql://unused", key, backup)

    assert mysql_backup.verify_backup(key, backup) == manifest
    assert dump not in backup.read_bytes()
    assert manifest["encrypted_sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert backup.stat().st_mode & 0o777 == 0o600

    backup.write_bytes(backup.read_bytes()[:-1] + b"x")
    with pytest.raises(ValueError, match="checksum mismatch"):
        mysql_backup.verify_backup(key, backup)


def test_backup_refuses_to_overwrite_existing_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mysql_backup,
        "dump_database",
        lambda _url: b"CREATE TABLE `users` (`id` int);",
    )
    backup = Path(tmp_path / "existing.sql.enc")
    backup.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        mysql_backup.create_backup(
            "mysql://unused", Fernet.generate_key().decode("ascii"), backup
        )


def test_dump_uses_owner_only_option_file_and_never_places_password_in_argv(
    monkeypatch,
):
    observed = {}

    def fake_run(command, **kwargs):
        option_path = Path(command[1].split("=", 1)[1])
        observed["command"] = command
        observed["mode"] = option_path.stat().st_mode & 0o777
        observed["options"] = option_path.read_text()
        return type("Result", (), {"stdout": b"CREATE TABLE `users` (`id` int);"})()

    monkeypatch.setattr(mysql_backup.subprocess, "run", fake_run)
    mysql_backup.dump_database(
        "mysql+pymysql://archive:highly-secret@mysql.internal/trainspotting"
    )

    assert observed["mode"] == 0o600
    assert "highly-secret" not in " ".join(observed["command"])
    assert "password=highly-secret" in observed["options"]


def test_restore_requires_empty_target_and_streams_plaintext(monkeypatch, tmp_path):
    dump = b"CREATE TABLE `users` (`id` int);"
    key = Fernet.generate_key().decode("ascii")
    backup = tmp_path / "restore.sql.enc"
    monkeypatch.setattr(mysql_backup, "dump_database", lambda _url: dump)
    mysql_backup.create_backup("mysql://unused", key, backup)
    table_results = iter([set(), mysql_backup.REQUIRED_TABLES])
    monkeypatch.setattr(
        mysql_backup, "database_tables", lambda _config, _credentials: next(table_results)
    )
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["input"] = kwargs["input"]
        return type("Result", (), {"stdout": b""})()

    monkeypatch.setattr(mysql_backup.subprocess, "run", fake_run)
    result = mysql_backup.restore_backup(
        "mysql+pymysql://archive:secret@mysql.internal/trainspotting_restore",
        key,
        backup,
    )

    assert result["restored_table_count"] == len(mysql_backup.REQUIRED_TABLES)
    assert observed["input"] == dump
    assert "secret" not in " ".join(observed["command"])


def test_restore_refuses_nonempty_target_before_import(monkeypatch, tmp_path):
    dump = b"CREATE TABLE `users` (`id` int);"
    key = Fernet.generate_key().decode("ascii")
    backup = tmp_path / "restore.sql.enc"
    monkeypatch.setattr(mysql_backup, "dump_database", lambda _url: dump)
    mysql_backup.create_backup("mysql://unused", key, backup)
    monkeypatch.setattr(
        mysql_backup,
        "database_tables",
        lambda _config, _credentials: {"existing_table"},
    )

    with pytest.raises(ValueError, match="empty database"):
        mysql_backup.restore_backup(
            "mysql+pymysql://archive:secret@mysql.internal/trainspotting_restore",
            key,
            backup,
        )
