from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.schema import metadata


EXPECTED_TABLES = {
    "archive_state",
    "collection_credits",
    "collection_media",
    "collections",
    "designers",
    "submission_audit",
    "submission_decisions",
    "submission_promotions",
    "submission_sources",
    "submissions",
    "users",
}


def test_portable_metadata_creates_all_tables_constraints_and_indexes(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'schema.db'}")
    try:
        metadata.create_all(engine)
        inspector = inspect(engine)

        assert set(inspector.get_table_names()) == EXPECTED_TABLES
        assert {index["name"] for index in inspector.get_indexes("submissions")} == {
            "idx_submissions_queue",
            "idx_submissions_submitter",
        }
        assert {
            foreign_key["referred_table"]
            for foreign_key in inspector.get_foreign_keys("submission_promotions")
        } == {"submissions", "users"}
        assert {
            foreign_key["referred_table"]
            for foreign_key in inspector.get_foreign_keys("collection_credits")
        } == {"collections", "designers"}
        assert {
            index["name"]
            for index in inspector.get_indexes("collection_credits")
        } == {
            "idx_collection_credits_collection",
            "idx_collection_credits_designer",
        }
        assert {
            constraint["name"]
            for constraint in inspector.get_check_constraints(
                "collection_credits"
            )
        } == {
            "ck_collection_credits_attribution_note_not_blank",
            "ck_collection_credits_order_positive",
            "ck_collection_credits_valid_role",
        }
        constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("archive_state")
        }
        assert constraints == {
            "ck_archive_state_singleton",
            "ck_archive_state_version_positive",
        }
    finally:
        engine.dispose()


def test_every_table_compiles_for_mysql_8():
    dialect = mysql.dialect()

    statements = [
        str(CreateTable(table).compile(dialect=dialect))
        for table in metadata.sorted_tables
    ]

    assert len(statements) == len(EXPECTED_TABLES)
    assert all("CREATE TABLE" in statement for statement in statements)
    assert all(
        "AUTO_INCREMENT" in statement
        for statement in statements
        if "archive_state" not in statement
    )
    assert all("ENGINE=InnoDB" in statement for statement in statements)
    assert all("CHARSET=utf8mb4" in statement for statement in statements)
