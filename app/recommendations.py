import re


STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "collection",
    "for",
    "from",
    "into",
    "its",
    "that",
    "the",
    "their",
    "this",
    "through",
    "was",
    "were",
    "with",
}


def meaningful_terms(collection: dict) -> set[str]:
    """Return normalized, useful words from public editorial metadata."""
    text = " ".join(
        value for value in (collection.get("name"), collection.get("description"))
        if value
    )
    terms = {
        term
        for term in re.findall(r"[a-z0-9]+", text.casefold())
        if len(term) >= 4 and term not in STOP_WORDS and not term.isdigit()
    }
    credited_name_terms = {
        term
        for credit in collection.get("credits", [])
        for term in re.findall(r"[a-z0-9]+", credit["designer_name"].casefold())
    }
    return terms - credited_name_terms


def rank_related_collections(
    target: dict,
    candidates: list[dict],
    *,
    limit: int,
) -> list[dict]:
    """Rank collections using deterministic, human-explainable public signals."""
    target_credits = {
        credit["designer_id"]: credit["designer_name"]
        for credit in target.get("credits", [])
    }
    target_terms = meaningful_terms(target)
    ranked = []

    for candidate in candidates:
        if candidate["id"] == target["id"]:
            continue

        score = 0
        reasons = []
        candidate_credits = {
            credit["designer_id"]: credit["designer_name"]
            for credit in candidate.get("credits", [])
        }
        shared_contributors = sorted(
            set(target_credits) & set(candidate_credits),
            key=lambda designer_id: (
                target_credits[designer_id].casefold(),
                designer_id,
            ),
        )
        if shared_contributors:
            score += 6 * len(shared_contributors)
            names = [target_credits[designer_id] for designer_id in shared_contributors]
            reasons.append(f"Shared contributor: {', '.join(names)}")

        if candidate["label"].casefold() == target["label"].casefold():
            score += 5
            reasons.append(f"Same label: {target['label']}")

        if candidate["season"].casefold() == target["season"].casefold():
            score += 3
            reasons.append(f"Same season: {target['season']}")

        year_distance = abs(candidate["release_year"] - target["release_year"])
        if year_distance == 0:
            score += 3
            reasons.append(f"Same release year: {target['release_year']}")
        elif year_distance <= 2:
            score += 3 - year_distance
            unit = "year" if year_distance == 1 else "years"
            reasons.append(f"Released {year_distance} {unit} apart")

        shared_terms = sorted(target_terms & meaningful_terms(candidate))[:3]
        if shared_terms:
            score += len(shared_terms)
            reasons.append(f"Shared terms: {', '.join(shared_terms)}")

        if score:
            ranked.append({**candidate, "score": score, "reasons": reasons})

    ranked.sort(
        key=lambda collection: (
            -collection["score"],
            -collection["release_year"],
            collection["id"],
        )
    )
    return ranked[:limit]
