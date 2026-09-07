"""Allow Vimeo collection media."""

from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _replace_media_type_constraint(
    values: str,
    *,
    existing_name: str,
    replacement_name: str,
) -> None:
    with op.batch_alter_table("collection_media") as batch_op:
        batch_op.drop_constraint(
            existing_name,
            type_="check",
        )
        batch_op.create_check_constraint(
            replacement_name,
            f"media_type IN ({values})",
        )


def upgrade():
    _replace_media_type_constraint(
        "'source', 'youtube', 'vimeo'",
        existing_name="ck_collection_media_valid_media_type",
        replacement_name="valid_media_type",
    )


def downgrade():
    op.execute("DELETE FROM collection_media WHERE media_type = 'vimeo'")
    _replace_media_type_constraint(
        "'source', 'youtube'",
        existing_name="valid_media_type",
        replacement_name="ck_collection_media_valid_media_type",
    )
