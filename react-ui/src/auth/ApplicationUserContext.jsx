/* eslint-disable react/only-export-components */
import { useAuth } from "@clerk/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { apiRequest } from "../api";

const ApplicationUserContext = createContext(null);

export function ApplicationUserProvider({ children }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [appUser, setAppUser] = useState(null);
  const [error, setError] = useState("");

  const authorizedRequest = useCallback(async (path, options = {}) => {
    const token = await getToken();
    if (!token) throw new Error("Authentication is required.");

    return apiRequest(path, {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      },
    });
  }, [getToken]);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setAppUser(null);
      setError("");
      return;
    }

    let cancelled = false;
    setError("");

    authorizedRequest("/me")
      .then((user) => {
        if (!cancelled) setAppUser(user);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setAppUser(null);
          setError(requestError.message || "Account sync failed.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authorizedRequest, isLoaded, isSignedIn]);

  const value = useMemo(() => ({
    appUser,
    authorizedRequest,
    error,
    isAdmin: appUser?.role === "admin",
    isLoading: !isLoaded || (Boolean(isSignedIn) && !appUser && !error),
    isSignedIn: Boolean(isSignedIn),
  }), [appUser, authorizedRequest, error, isLoaded, isSignedIn]);

  return (
    <ApplicationUserContext.Provider value={value}>
      {children}
    </ApplicationUserContext.Provider>
  );
}

export function useApplicationUser() {
  const context = useContext(ApplicationUserContext);
  if (!context) {
    throw new Error("useApplicationUser must be used within ApplicationUserProvider.");
  }
  return context;
}
