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

STRONG_MATCH_MINIMUM = 14
NOTABLE_MATCH_MINIMUM = 9

EDITORIAL_FACETS = {
    "theme": {
        "craft": ("craft", "craftsmanship", "handmade"),
        "futurism": ("future", "futurism", "futurist", "futuristic"),
        "gender": ("gender", "genderless", "androgyny", "androgynous"),
        "glamour": ("glamour", "glamorous"),
        "romanticism": ("romantic", "romanticism"),
        "sportswear": ("sportswear", "athletic"),
        "theatricality": ("theatrical", "theatricality", "spectacle"),
        "uniform": ("uniform", "uniforms"),
        "utility": ("utility", "utilitarian", "workwear"),
    },
    "motif": {
        "animal print": ("animal print", "leopard", "zebra"),
        "floral": ("floral", "florals", "flower", "flowers"),
        "graphic": ("graphic", "graphics"),
        "logo": ("logo", "logos", "monogram"),
        "military": ("military",),
        "religious imagery": ("religious", "ecclesiastical", "devotional"),
    },
    "material": {
        "denim": ("denim",),
        "feathers": ("feather", "feathers", "feathered"),
        "fur": ("fur", "furs"),
        "knitwear": ("knit", "knits", "knitwear", "knitted"),
        "lace": ("lace",),
        "latex": ("latex",),
        "leather": ("leather", "leathers"),
        "metal": ("metal", "metallic", "metalwork"),
        "silk": ("silk", "silks"),
        "tulle": ("tulle",),
        "velvet": ("velvet",),
        "wool": ("wool", "woolen", "woollen"),
    },
    "texture": {
        "distressed": ("distressed", "distressing"),
        "embellished": ("embellished", "embellishment", "embellishments"),
        "layered": ("layered", "layering", "layers"),
        "pleated": ("pleat", "pleats", "pleated", "pleating"),
        "quilted": ("quilted", "quilting"),
        "sheer": ("sheer", "transparency", "transparent"),
    },
    "color": {
        "black": ("black",),
        "blue": ("blue",),
        "gold": ("gold", "golden"),
        "green": ("green",),
        "monochrome": ("monochrome", "monochromatic"),
        "neon": ("neon",),
        "pink": ("pink",),
        "red": ("red",),
        "silver": ("silver",),
        "white": ("white",),
    },
    "silhouette": {
        "asymmetric": ("asymmetry", "asymmetric", "asymmetrical"),
        "elongated": ("elongated",),
        "oversized": ("oversized", "oversize"),
        "sculptural": ("sculptural", "sculpted"),
        "tailored": ("tailoring", "tailored"),
        "voluminous": ("volume", "voluminous"),
    },
}

EDITORIAL_WEIGHTS = {
    "theme": 5,
    "motif": 5,
    "material": 5,
    "texture": 4,
    "color": 4,
    "silhouette": 3,
}

DIVERSITY_SCORE_WINDOW = 2
BLACK_COLOR_CONTEXT = re.compile(
    r"(?:\bblack\b(?:\s+[a-z]+){0,2}\s+"
    r"(?:coat|coats|denim|dress|dresses|fabric|fabrics|garment|garments|"
    r"knit|knits|lace|latex|leather|silk|suit|suits|tailoring|textile|textiles|"
    r"tulle|velvet|wool)\b|"
    r"\b(?:coat|coats|denim|dress|dresses|fabric|fabrics|garment|garments|"
    r"knit|knits|lace|latex|leather|silk|suit|suits|tailoring|textile|textiles|"
    r"tulle|velvet|wool)(?:\s+[a-z]+){0,2}\s+black\b)"
)


def match_strength(score: int) -> str:
    """Translate a transparent relevance score into visitor-friendly language."""
    if score >= STRONG_MATCH_MINIMUM:
        return "Strong"
    if score >= NOTABLE_MATCH_MINIMUM:
        return "Notable"
    return "Contextual"


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


def editorial_facets(collection: dict) -> dict[str, set[str]]:
    """Extract auditable editorial descriptors from curated public copy."""
    text = " ".join(
        value for value in (collection.get("name"), collection.get("description"))
        if value
    ).casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", text).strip()
    facets: dict[str, set[str]] = {}
    for descriptor in collection.get("descriptors", []):
        category = descriptor.get("category")
        value = descriptor.get("canonical_value")
        if category in EDITORIAL_FACETS and value in EDITORIAL_FACETS[category]:
            facets.setdefault(category, set()).add(value)
    for category, descriptors in EDITORIAL_FACETS.items():
        matches = {
            descriptor
            for descriptor, aliases in descriptors.items()
            if any(
                (
                    BLACK_COLOR_CONTEXT.search(normalized)
                    if category == "color" and descriptor == "black"
                    else re.search(rf"\b{re.escape(alias)}\b", normalized)
                )
                for alias in aliases
            )
        }
        if matches:
            facets.setdefault(category, set()).update(matches)
    return facets


def _diversify(ranked: list[dict], limit: int) -> list[dict]:
    """Choose near-equal results without letting one house dominate the set."""
    remaining = list(ranked)
    selected = []
    selected_labels: dict[str, int] = {}
    selected_designers: dict[int, int] = {}
    while remaining and len(selected) < limit:
        best_score = remaining[0]["score"]
        comparable = [
            candidate
            for candidate in remaining
            if candidate["score"] >= best_score - DIVERSITY_SCORE_WINDOW
        ]

        def repetition(candidate):
            label_repetitions = selected_labels.get(candidate["label"].casefold(), 0)
            designer_repetitions = sum(
                selected_designers.get(credit["designer_id"], 0)
                for credit in candidate.get("credits", [])
            )
            return (
                label_repetitions + designer_repetitions,
                label_repetitions,
                designer_repetitions,
                -candidate["score"],
                -candidate["release_year"],
                candidate["id"],
            )

        chosen = min(comparable, key=repetition)
        selected.append(chosen)
        selected_labels[chosen["label"].casefold()] = (
            selected_labels.get(chosen["label"].casefold(), 0) + 1
        )
        for credit in chosen.get("credits", []):
            designer_id = credit["designer_id"]
            selected_designers[designer_id] = selected_designers.get(designer_id, 0) + 1
        remaining.remove(chosen)

    selected.sort(
        key=lambda collection: (
            -collection["score"],
            -collection["release_year"],
            collection["id"],
        )
    )
    return selected


def editorial_search_terms(collection: dict) -> set[str]:
    """Return aliases that can retrieve normalized editorial matches in SQL."""
    facets = editorial_facets(collection)
    return {
        alias
        for category, descriptors in EDITORIAL_FACETS.items()
        for descriptor in facets.get(category, set())
        for alias in descriptors[descriptor]
    }


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
    target_facets = editorial_facets(target)
    ranked = []
    seen_ids = set()

    for candidate in candidates:
        if candidate["id"] == target["id"] or candidate["id"] in seen_ids:
            continue
        seen_ids.add(candidate["id"])

        score = 0
        reasons = []
        candidate_facets = editorial_facets(candidate)
        has_editorial_match = False
        for category, weight in EDITORIAL_WEIGHTS.items():
            shared_descriptors = sorted(
                target_facets.get(category, set())
                & candidate_facets.get(category, set())
            )
            if shared_descriptors:
                has_editorial_match = True
                score += weight * len(shared_descriptors)
                reasons.append(
                    f"Shared {category}: {', '.join(shared_descriptors)}"
                )

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
        has_identity_match = bool(shared_contributors)
        if shared_contributors:
            score += 3 * len(shared_contributors)
            names = [target_credits[designer_id] for designer_id in shared_contributors]
            reasons.append(f"Shared contributor: {', '.join(names)}")

        same_label = candidate["label"].casefold() == target["label"].casefold()
        if same_label:
            score += 2
            reasons.append(f"Same label: {target['label']}")

        if candidate["season"].casefold() == target["season"].casefold():
            score += 1
            reasons.append(f"Same season: {target['season']}")

        year_distance = abs(candidate["release_year"] - target["release_year"])
        if year_distance == 0:
            score += 1
            reasons.append(f"Same release year: {target['release_year']}")
        elif year_distance <= 2:
            score += 1
            unit = "year" if year_distance == 1 else "years"
            reasons.append(f"Released {year_distance} {unit} apart")

        shared_terms = sorted(target_terms & meaningful_terms(candidate))[:3]
        editorial_terms = {
            alias
            for category, descriptors in EDITORIAL_FACETS.items()
            for descriptor in target_facets.get(category, set())
            for alias in descriptors[descriptor]
            if " " not in alias
        }
        shared_terms = [term for term in shared_terms if term not in editorial_terms]
        if shared_terms:
            score += len(shared_terms)
            reasons.append(f"Shared terms: {', '.join(shared_terms)}")

        # Season and release proximity are useful context, but are too broad to
        # establish a relationship by themselves across the full archive.
        if not (has_editorial_match or has_identity_match or same_label):
            continue

        ranked.append(
            {
                **candidate,
                "score": score,
                "match_strength": match_strength(score),
                "reasons": reasons,
            }
        )

    ranked.sort(
        key=lambda collection: (
            -collection["score"],
            -collection["release_year"],
            collection["id"],
        )
    )
    return _diversify(ranked, limit)
