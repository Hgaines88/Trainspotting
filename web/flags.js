const FLAGS_BY_NATIONALITY = {
        American: "🇺🇸",
        Belgian: "🇧🇪",
        British: "🇬🇧",
        "British-Jamaican": "🇬🇧 🇯🇲",
        Canadian: "🇨🇦",
        "Dominican-American": "🇩🇴 🇺🇸",
        French: "🇫🇷",
        "French-American": "🇫🇷 🇺🇸",
        "French-Belgian": "🇫🇷 🇧🇪",
        "French-Colombian": "🇫🇷 🇨🇴",
        Georgian: "🇬🇪",
        German: "🇩🇪",
        Italian: "🇮🇹",
        Japanese: "🇯🇵",
        "Liberian-American": "🇱🇷 🇺🇸",
        "Northern Irish": "🇬🇧",
        Russian: "🇷🇺",
        Argentine: "🇦🇷", Australian: "🇦🇺", Austrian: "🇦🇹", Brazilian: "🇧🇷",
        Chinese: "🇨🇳", Colombian: "🇨🇴", Croatian: "🇭🇷", Czech: "🇨🇿",
        Danish: "🇩🇰", Dominican: "🇩🇴", Dutch: "🇳🇱", Finnish: "🇫🇮",
        Ghanaian: "🇬🇭", Greek: "🇬🇷", Indian: "🇮🇳", Irish: "🇮🇪",
        Israeli: "🇮🇱", Jamaican: "🇯🇲", Korean: "🇰🇷", Lebanese: "🇱🇧",
        Liberian: "🇱🇷", Mexican: "🇲🇽", Moroccan: "🇲🇦", Nigerian: "🇳🇬",
        Norwegian: "🇳🇴", Polish: "🇵🇱", Portuguese: "🇵🇹", Romanian: "🇷🇴",
        Scottish: "🏴󠁧󠁢󠁳󠁣󠁴󠁿", Senegalese: "🇸🇳", Serbian: "🇷🇸", Spanish: "🇪🇸",
        Swedish: "🇸🇪", Swiss: "🇨🇭", Turkish: "🇹🇷", Ukrainian: "🇺🇦",
        Welsh: "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "South Korean": "🇰🇷",
    };

function nationalityFlags(nationality) {
    if (typeof nationality !== "string") return "";
    const supported = Object.keys(FLAGS_BY_NATIONALITY);
    const findMatch = (value) => supported.find(
        (candidate) => candidate.toLowerCase() === value.trim().toLowerCase()
    );
    const exact = findMatch(nationality);
    if (exact) return FLAGS_BY_NATIONALITY[exact];
    const compound = nationality.split(/\s*[-/]\s*/).map((part) => {
        const match = findMatch(part);
        return match ? FLAGS_BY_NATIONALITY[match] : "";
    });
    return compound.length > 1 && compound.every(Boolean)
        ? [...new Set(compound)].join(" ")
        : "";
}

if (typeof module !== "undefined") {
    module.exports = { nationalityFlags };
}
