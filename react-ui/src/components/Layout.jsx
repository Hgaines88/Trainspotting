import { Link, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/">
          <span>TRAINSPOTTING</span>
          <small>FASHION HISTORY IN MOTION</small>
        </Link>
        <div className="signal-stack">
          <div className="signal">
            <i aria-hidden="true" /> LIVE DATABASE <span>CH. 001</span>
          </div>
          <span className="header-signature" aria-label="Created by H Gaines">
            (h)gaines.
          </span>
        </div>
      </header>
      <div className="ticker" aria-hidden="true">
        <span>
          DESIGNER → LABEL → SEASON → IMAGE → MOVEMENT → MEMORY → DESIGNER →
          LABEL → SEASON → IMAGE → MOVEMENT → MEMORY →
        </span>
      </div>
      <main className="page">
        <Outlet />
      </main>
      <footer className="site-footer">
        <span>PUBLIC ACCESS / OPEN ARCHIVE</span>
        <span className="digital-signature" aria-label="Created by H Gaines">
          (h)gaines.
        </span>
        <span>NYC — {new Date().getFullYear()}</span>
      </footer>
    </div>
  );
}
