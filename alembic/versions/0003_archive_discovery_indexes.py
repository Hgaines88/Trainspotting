"""Add indexes used by archive discovery filters and stable sorting."""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    indexes = (
        ("idx_designers_nationality", "designers", ["nationality"]),
        ("idx_collections_label", "collections", ["label"]),
        ("idx_collections_season", "collections", ["season"]),
        (
            "idx_collections_year_status",
            "collections",
            ["release_year", "status"],
        ),
    )
    inspector = sa.inspect(op.get_bind())
    indexes_by_table = {
        table: {index["name"] for index in inspector.get_indexes(table)}
        for table in {table for _, table, _ in indexes}
    }
    for name, table, columns in indexes:
        if name not in indexes_by_table[table]:
            op.create_index(name, table, columns)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, names in (
        (
            "collections",
            (
                "idx_collections_year_status",
                "idx_collections_season",
                "idx_collections_label",
            ),
        ),
        ("designers", ("idx_designers_nationality",)),
    ):
        existing = {index["name"] for index in inspector.get_indexes(table)}
        for name in names:
            if name in existing:
                op.drop_index(name, table_name=table)
