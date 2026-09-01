import { useAuth } from "@clerk/react";
import { useEffect, useState } from "react";
import { apiRequest } from "../api";

export default function UserSync() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      setError("");
      return;
    }

    let cancelled = false;

    async function synchronizeUser() {
      try {
        const token = await getToken();
        if (!token) throw new Error("Clerk did not provide a session token.");

        await apiRequest("/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!cancelled) setError("");
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message || "Account sync failed.");
        }
      }
    }

    synchronizeUser();
    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn]);

  if (!error) return null;

  return (
    <span className="auth-sync-error" role="status" title={error}>
      Account sync unavailable
    </span>
  );
}
