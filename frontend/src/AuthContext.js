import React, { createContext, useContext, useState, useEffect } from "react";
import supabaseClient from "./supabaseClient";
import posthog from "posthog-js";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch initial session
    const fetchSession = async () => {
      const { data: { session } } = await supabaseClient.auth.getSession();
      const sessionUser = session?.user || null;
      setUser(sessionUser);
      if (sessionUser) {
        posthog.identify(sessionUser.id);
      }
      setLoading(false);
    };
    fetchSession();

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
