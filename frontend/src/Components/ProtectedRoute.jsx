import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const ProtectedRoute = ({ children, openModal }) => {
  const { user } = useAuth();
  // const [redirecting, setRedirecting] = useState(false);

  // useEffect(() => {
  //   if (!user && !redirecting) {
  //     setRedirecting(true); // Prevent duplicate modal triggers
  //     setTimeout(() => {
  //       console.log(`"Modal triggered": ${user}`);
  //       openModal("Access Denied", "You need to be logged in to do that!");
  //     }, 0); // Slight delay to wait for navigation
  //   }
  // }, [user, redirecting, openModal]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;
