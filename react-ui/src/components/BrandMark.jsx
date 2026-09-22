const BRAND_NAME = "TRAINSPOTTING";

export default function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span className="brand-route">TS</span>
      <span className="brand-wordmark">
        {Array.from(BRAND_NAME, (letter, index) => (
          <span className="brand-letter" key={`${letter}-${index}`}>{letter}</span>
        ))}
      </span>
      <span className="brand-direction">→</span>
    </span>
  );
}
