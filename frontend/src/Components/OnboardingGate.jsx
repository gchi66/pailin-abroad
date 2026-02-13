import React, { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { useAuth } from "../AuthContext";

const ONBOARDING_PATHS = [
  "/onboarding",
  "/verify-email",
  "/email-confirmation",
  "/reset-password",
  "/checkout",
  "/payment-success"
];

const OnboardingGate = ({ children }) => {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const checkOnboarding = async () => {
      if (!user) return;
      if (ONBOARDING_PATHS.some((path) => location.pathname.startsWith(path))) return;

      const { data: profile, error } = await supabaseClient
        .from("users")
        .select("onboarding_completed")
        .eq("id", user.id)
        .single();

      if (error) {
        console.error("Error checking onboarding status:", error);
        return;
      }

      if (!profile?.onboarding_completed) {
        navigate("/onboarding", { replace: true });
      }
    };

    checkOnboarding();
  }, [user, location.pathname, navigate]);

  return children;
};

export default OnboardingGate;
