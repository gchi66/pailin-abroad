import React, { useRef } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const RestrictedRoute = ({ children, openModal }) => {
  const { user } = useAuth();
  const hasTriggeredModal = useRef(false);

  if (user) {
    // Trigger modal and redirect to the profile page
    if (!hasTriggeredModal.current) {
      openModal("Already Signed In", "You are already signed in!");
      hasTriggeredModal.current = true; // Prevent re-triggering
    }
    return <Navigate to="/profile" replace />;
  }

  return children;
};

export default RestrictedRoute;
