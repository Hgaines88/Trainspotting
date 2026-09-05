export function collectionCreditNames(collection) {
  const names = collection.credits
    ?.map((credit) => credit.designer_name)
    .filter(Boolean);
  if (names?.length) return names;
  return collection.lead_designer ? [collection.lead_designer] : [];
}


export function collectionCreditLine(collection) {
  return collectionCreditNames(collection).join(" + ");
}
