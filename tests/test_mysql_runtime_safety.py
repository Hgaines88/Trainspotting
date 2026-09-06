import pytest

from tests.test_mysql_runtime import require_disposable_mysql_test_database


def test_runtime_tests_accept_a_dedicated_test_database():
    require_disposable_mysql_test_database(
        "mysql+pymysql://user:secret@mysql/trainspotting_test?charset=utf8mb4"
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "mysql+pymysql://user:secret@mysql/trainspotting",
        "mysql+pymysql://user:secret@mysql/staging",
        "mysql+pymysql://user:secret@mysql/production",
        "mysql+pymysql://user:secret@mysql",
        "sqlite+pysqlite:///trainspotting_test",
    ],
)
def test_runtime_tests_reject_unsafe_database_urls(database_url):
    with pytest.raises(RuntimeError, match="refusing to modify"):
        require_disposable_mysql_test_database(database_url)
