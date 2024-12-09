import React from "react";
import { Navigate} from "react-router-dom";
import { useAuth } from "../AuthContext";

const RestrictedRoute = ({ children }) => {
  const { user } = useAuth();
  // const location = useLocation();
  // const modalTriggeredRef = useRef(false); // To track if the modal has been triggered

  // // Suppress the modal if the user is navigating from the login page
  // if (user && location.pathname) {
  //   console.log(`Location: ${location}`);
  //   if (!modalTriggeredRef.current) {
  //     openModal("Already Signed In", "You are already signed in!");
  //     modalTriggeredRef.current = true; // Set the flag to prevent re-triggering
  //   }
  //   return <Navigate to="/profile" replace />;
  // }

  if (user) {
    return <Navigate to="/profile" replace />;
  }

  return children;
};

export default RestrictedRoute;
