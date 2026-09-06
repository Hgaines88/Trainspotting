from app.naming import normalized_search_name


def test_search_name_normalization_is_accent_and_punctuation_insensitive():
    assert normalized_search_name("  Cristóbal—Balenciaga! ") == (
        "cristobal balenciaga"
    )


def test_search_name_normalization_does_not_invent_content():
    assert normalized_search_name("***") == ""
