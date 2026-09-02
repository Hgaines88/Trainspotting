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

export const SUPPORTED_NATIONALITIES = Object.keys(FLAGS_BY_NATIONALITY).sort();

export function nationalityFlags(nationality) {
  if (typeof nationality !== "string") return "";
  const findMatch = (value) => SUPPORTED_NATIONALITIES.find(
    (candidate) => candidate.toLocaleLowerCase() === value.trim().toLocaleLowerCase(),
  );
  const exact = findMatch(nationality);
  if (exact) return FLAGS_BY_NATIONALITY[exact];

  const compoundFlags = nationality.split(/\s*[-/]\s*/).map((part) => {
    const match = findMatch(part);
    return match ? FLAGS_BY_NATIONALITY[match] : "";
  });
  return compoundFlags.length > 1 && compoundFlags.every(Boolean)
    ? [...new Set(compoundFlags)].join(" ")
    : "";
}
