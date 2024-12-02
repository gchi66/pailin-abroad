import React, { createContext, useContext, useState, useEffect } from "react";
import supabaseClient from "./supabaseClient";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch initial session
    const fetchSession = async () => {
      const { data: { session } } = await supabaseClient.auth.getSession();
      setUser(session?.user || null);
      setLoading(false);
    };
    fetchSession();

    // Listen for session changes
    const { data: authListener } = supabaseClient.auth.onAuthStateChange((event, session) => {
      console.log("Auth state changed:", event, session);
      setUser(session?.user || null); // Update user state
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
