const BRAND_NAME = "TRAINSPOTTING";

export default function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span className="brand-primary">
        <span className="brand-wordmark">
          {Array.from(BRAND_NAME, (letter, index) => (
            <span className="brand-letter" key={`${letter}-${index}`}>{letter}</span>
          ))}
        </span>
        <span className="brand-route"><b>TS</b></span>
        <span className="brand-direction"><i /></span>
      </span>
      <span className="brand-meta">
        <span className="brand-tagline"><i />FASHION HISTORY IN MOTION</span>
        <span className="brand-service-line">
          <span className="brand-track brand-track-t" />
          <span className="brand-track brand-track-s" />
          <span className="brand-track brand-track-x" />
          <i /><i /><b /><i /><i />
        </span>
        <span className="brand-service-markers">
          <b className="route-t">T</b><b className="route-s">S</b><b className="route-x">X</b>
        </span>
        <span className="brand-destinations">UPTOWN<br />DOWNTOWN</span>
      </span>
    </span>
  );
}
