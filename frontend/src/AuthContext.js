import React, { createContext, useContext, useState, useEffect } from "react";
import supabaseClient from "./supabaseClient";
import posthog from "posthog-js";

const AuthContext = createContext();
const AUTH_SESSION_TIMEOUT_MS = 10000;

const getSessionWithTimeout = async () => {
  let timeoutId;
  try {
    return await Promise.race([
      supabaseClient.auth.getSession(),
      new Promise((_, reject) => {
        timeoutId = window.setTimeout(
          () => reject(new Error("Authentication session timed out.")),
          AUTH_SESSION_TIMEOUT_MS
        );
      }),
    ]);
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch initial session
    const fetchSession = async () => {
      try {
        const { data: { session }, error } = await getSessionWithTimeout();
        if (error) throw error;

        const sessionUser = session?.user || null;
        setUser(sessionUser);
        if (sessionUser) {
          posthog.identify(sessionUser.id);
        }
      } catch (sessionError) {
        console.error("Unable to restore authentication session:", sessionError);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    void fetchSession();

    // Listen for session changes
    const { data: authListener } = supabaseClient.auth.onAuthStateChange((event, session) => {
      const nextUser = session?.user || null;
      setUser(nextUser);
      if (nextUser) {
        posthog.identify(nextUser.id);
      } else if (event === "SIGNED_OUT") {
        posthog.reset();
      }
    });

    return () => authListener.subscription.unsubscribe(); // Cleanup listener
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
