from app.recommendations import rank_related_collections


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
    assert results[0]["score"] == 19
    assert results[0]["reasons"] == [
        "Shared contributor: Lead Designer",
        "Same label: House One",
        "Same season: Spring/Summer",
        "Released 1 year apart",
        "Shared terms: evening, sculptural, tailoring",
    ]
    assert results[1]["reasons"] == [
        "Released 1 year apart",
        "Shared terms: sculptural",
    ]


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
