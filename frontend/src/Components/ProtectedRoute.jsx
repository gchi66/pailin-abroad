import React, { useRef } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const ProtectedRoute = ({ children, openModal }) => {
  const { user } = useAuth();
  const hasTriggeredModal = useRef(false);

  if (!user) {
    // Trigger modal and redirect to the login page
    if (!hasTriggeredModal.current) {
      openModal("You need to be logged in to do that!");
      hasTriggeredModal.current = true; // Prevent re-triggering
    }
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;
