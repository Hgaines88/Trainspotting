from app.recommendations import (
    editorial_facets,
    editorial_search_terms,
    rank_related_collections,
)


def collection(
    collection_id,
    *,
    designer_id=1,
    designer_name="Lead Designer",
    label="House One",
    season="Spring/Summer",
    release_year=2024,
    name=None,
    description=None,
):
    return {
        "id": collection_id,
        "designer_id": designer_id,
        "lead_designer": designer_name,
        "label": label,
        "season": season,
        "release_year": release_year,
        "name": name,
        "description": description,
        "credits": [
            {
                "designer_id": designer_id,
                "designer_name": designer_name,
                "role": "lead",
                "position": 1,
                "attribution_note": None,
            }
        ],
    }


def test_related_collections_rank_stronger_matches_and_explain_each_signal():
    target = collection(
        1,
        name="Sculptural Tailoring",
        description="Architectural evening silhouettes",
    )
    strongest = collection(
        2,
        release_year=2023,
        name="Sculptural Forms",
        description="Evening tailoring",
    )
    nearby = collection(
        3,
        designer_id=2,
        designer_name="Guest Designer",
        label="House Two",
        season="Autumn/Winter",
        release_year=2025,
        description="Sculptural sportswear",
    )

    results = rank_related_collections(target, [nearby, target, strongest], limit=10)

    assert [result["id"] for result in results] == [2, 3]
    assert results[0]["score"] == 14
    assert results[0]["match_strength"] == "Strong"
    assert results[0]["reasons"] == [
        "Shared silhouette: sculptural, tailored",
        "Shared contributor: Lead Designer",
        "Same label: House One",
        "Same season: Spring/Summer",
        "Released 1 year apart",
        "Shared terms: evening",
    ]
    assert results[1]["reasons"] == [
        "Shared silhouette: sculptural",
        "Released 1 year apart",
    ]
    assert results[1]["match_strength"] == "Contextual"


def test_contributor_names_are_not_repeated_as_shared_text_terms():
    target = collection(1, description="Lead Designer explores tailoring")
    candidate = collection(2, description="A retrospective for Lead Designer")

    result = rank_related_collections(target, [candidate], limit=4)[0]

    assert result["reasons"] == [
        "Shared contributor: Lead Designer",
        "Same label: House One",
        "Same season: Spring/Summer",
        "Same release year: 2024",
    ]


def test_related_collections_use_stable_ties_limit_and_no_duplicates():
    target = collection(10, release_year=2020)
    older = collection(20, designer_id=2, release_year=2019)
    newer_high_id = collection(40, designer_id=3, release_year=2021)
    newer_low_id = collection(30, designer_id=4, release_year=2021)

    results = rank_related_collections(
        target,
        [newer_high_id, older, newer_low_id, target],
        limit=2,
    )

    assert [result["id"] for result in results] == [30, 40]
    assert len({result["id"] for result in results}) == len(results)


def test_sparse_unrelated_collections_are_omitted():
    target = collection(
        1,
        designer_id=1,
        label="House One",
        season="Resort",
        release_year=2000,
    )
    unrelated = collection(
        2,
        designer_id=2,
        label="House Two",
        season="Pre-Fall",
        release_year=2020,
    )

    assert rank_related_collections(target, [unrelated], limit=4) == []


def test_season_and_year_proximity_only_boost_an_established_relationship():
    target = collection(1, designer_id=1, label="House One", release_year=2024)
    superficially_close = collection(
        2,
        designer_id=2,
        designer_name="Unrelated Designer",
        label="House Two",
        release_year=2024,
    )

    assert rank_related_collections(target, [superficially_close], limit=4) == []


def test_match_strength_thresholds_are_stable_and_explainable():
    target = collection(
        1,
        release_year=2024,
        description="Black denim and leather tailoring study",
    )
    strong = collection(
        2,
        designer_id=2,
        designer_name="Another Designer",
        label="House Two",
        release_year=2023,
        description="Black leather and denim",
    )
    notable = collection(
        3,
        designer_id=3,
        designer_name="Third Designer",
        label="House Three",
        release_year=2023,
        description="Black denim",
    )
    contextual = collection(
        4,
        designer_id=4,
        designer_name="Fourth Designer",
        label="House Four",
        season="Autumn/Winter",
        release_year=2023,
        description="Tailoring study",
    )

    results = rank_related_collections(
        target,
        [contextual, notable, strong],
        limit=4,
    )

    assert {result["id"]: result["match_strength"] for result in results} == {
        2: "Strong",
        3: "Notable",
        4: "Contextual",
    }


def test_editorial_aliases_normalize_to_a_controlled_explanation():
    facets = editorial_facets(
        collection(
            1,
            description="Futuristic woollen knits use transparent layers and oversize forms",
        )
    )

    assert facets == {
        "theme": {"futurism"},
        "material": {"knitwear", "wool"},
        "texture": {"layered", "sheer"},
        "silhouette": {"oversized"},
    }


def test_editorial_search_terms_expand_only_detected_controlled_aliases():
    terms = editorial_search_terms(
        collection(
            1,
            description="Futuristic woollen knits use transparent layers and oversize forms",
        )
    )

    assert terms == {
        "future",
        "futurism",
        "futurist",
        "futuristic",
        "knit",
        "knits",
        "knitted",
        "knitwear",
        "layered",
        "layering",
        "layers",
        "oversize",
        "oversized",
        "sheer",
        "transparency",
        "transparent",
        "wool",
        "woolen",
        "woollen",
    }


def test_editorial_overlap_can_outrank_same_designer_and_label():
    target = collection(
        1,
        description="Black denim and leather",
        release_year=2024,
    )
    archival_neighbor = collection(2, release_year=2023)
    thematic_neighbor = collection(
        3,
        designer_id=2,
        designer_name="Different Designer",
        label="Different House",
        season="Autumn/Winter",
        release_year=2010,
        description="Black leather with denim panels",
    )

    results = rank_related_collections(
        target,
        [archival_neighbor, thematic_neighbor],
        limit=4,
    )

    assert [result["id"] for result in results] == [3, 2]
    assert results[0]["match_strength"] == "Strong"
    assert results[0]["reasons"][:2] == [
        "Shared material: denim, leather",
        "Shared color: black",
    ]
