/* eslint-disable react/only-export-components */
import { createContext, useContext, useMemo } from "react";


const STORAGE_KEY = "trainspotting-e2e-identity";
const AuthContext = createContext(null);


export function ClerkProvider({ children }) {
  const identity = window.localStorage.getItem(STORAGE_KEY);
  const value = useMemo(() => ({
    getToken: async () => (identity ? `e2e-${identity}` : null),
    isLoaded: true,
    isSignedIn: Boolean(identity),
  }), [identity]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth requires the E2E ClerkProvider.");
  return context;
}


export function Show({ children, when }) {
  const { isSignedIn } = useAuth();
  const visible = when === "signed-in" ? isSignedIn : !isSignedIn;
  return visible ? children : null;
}


export function SignInButton({ children }) {
  return children;
}


export function SignUpButton({ children }) {
  return children;
}


export function UserButton() {
  return <span aria-label="Synthetic E2E account">E2E</span>;
}
