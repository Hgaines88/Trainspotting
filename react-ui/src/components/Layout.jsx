import {
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/react";
import { Link, NavLink, Outlet } from "react-router-dom";
import UserSync from "./UserSync";
import { useApplicationUser } from "../auth/ApplicationUserContext";

export default function Layout() {
  const { appUser } = useApplicationUser();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to archive content</a>
      <header className="site-header">
        <Link className="brand" to="/">
          <span>TRAINSPOTTING</span>
          <small>FASHION HISTORY IN MOTION</small>
        </Link>
        <nav className="archive-navigation" aria-label="Public archive">
          <NavLink end to="/">Designers</NavLink>
          <NavLink to="/collections">Collections</NavLink>
        </nav>
        <div className="signal-stack">
          <div className="auth-controls" aria-label="Account controls">
            <UserSync />
            <Show when="signed-out">
              <SignInButton mode="modal">
                <button className="auth-button secondary" type="button">
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button className="auth-button" type="button">
                  Join
                </button>
              </SignUpButton>
            </Show>
            <Show when="signed-in">
              <Link className="auth-button secondary" to="/submissions/mine">Submissions</Link>
              {["moderator", "admin"].includes(appUser?.role) && <Link className="auth-button secondary" to="/moderation">Review</Link>}
              <span className="account-label">Account</span>
              <UserButton />
            </Show>
          </div>
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
      <main className="page" id="main-content" tabIndex={-1}>
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
