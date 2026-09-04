from scripts.sqlite_baseline import run_baseline


def test_sqlite_baseline_preserves_integrity_under_mixed_activity():
    result = run_baseline(reads=8, writes=4, workers=4)

    assert result["failures"] == []
    assert result["persisted_writes"] == 4
    assert result["integrity"] == "ok"
