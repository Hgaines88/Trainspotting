from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.schema import metadata


EXPECTED_TABLES = {
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
    assert all("AUTO_INCREMENT" in statement for statement in statements)
    assert all("ENGINE=InnoDB" in statement for statement in statements)
    assert all("CHARSET=utf8mb4" in statement for statement in statements)
