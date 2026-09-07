const PALETTES = [
  ["#b7ff00", "#152100", "#f1f1ec"],
  ["#ff5c35", "#2a0900", "#fff2e9"],
  ["#73c9ff", "#001a2b", "#eff9ff"],
  ["#d9a7ff", "#21072f", "#fbf2ff"],
  ["#ffd84d", "#281d00", "#fff9df"],
  ["#ff83b5", "#2b0716", "#fff0f6"],
];

export function collectionCoverIdentity(collection) {
  return [
    collection.id,
    collection.label,
    collection.season,
    collection.release_year,
  ].filter((value) => value !== null && value !== undefined).join("|");
}

export function collectionCoverStyle(collection) {
  const identity = collectionCoverIdentity(collection) || "trainspotting";
  let hash = 2166136261;
  for (const character of identity) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  const unsignedHash = hash >>> 0;
  const [accent, field, paper] = PALETTES[unsignedHash % PALETTES.length];
  return {
    "--cover-accent": accent,
    "--cover-field": field,
    "--cover-paper": paper,
    "--cover-angle": `${24 + (unsignedHash % 5) * 9}deg`,
    "--cover-shift": `${10 + (unsignedHash % 7) * 3}px`,
  };
}
