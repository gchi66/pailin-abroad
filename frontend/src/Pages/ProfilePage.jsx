import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
// import { useAuth } from "../AuthContext";
import "../Styles/ProfilePage.css";


const ProfilePage = () => {
  const navigate = useNavigate();
  const placeholderImage = "/images/Pailin.png";
  // const { user } = useAuth();
  const [profileImage, setProfileImage] = useState(placeholderImage);
  const [isImageSelectorOpen, setImageSelectorOpen] = useState(false);

  const availableImages = [
    "images/Chloe-blue.png",
    "images/Jamie-blue.png",
    "images/Mark-blue.png",
  ];

  const handleImageChange = (image) => {
    setProfileImage(image);
    setImageSelectorOpen(false);
  };

  const handleLogout = async () => {
    try {
      await supabaseClient.auth.signOut(); // Log the user out via Supabase
      navigate("/"); // Redirect to the home page
    } catch (error) {
      console.error("Logout Error:", error.message);
    }
  };

  const handleDelete = async () => {
    const confirmation = window.confirm(
      "Are you sure you want to delete your account? This action cannot be undone."
    );

    if (!confirmation) return;

    try {
      const {
        data: { session },
        error,
      } = await supabaseClient.auth.getSession(); // Retrieve session from Supabase

      if (error) {
        console.error("Error fetching session:", error.message);
        alert("Error fetching session. Please try again.");
        return;
      }

      if (session && session.access_token) {
        const accessToken = session.access_token;

        // Make a DELETE request to your backend route to delete the account
        const response = await fetch("http://127.0.0.1:5000/api/delete_account", {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ access_token: accessToken }), // Send the access token to your backend
        });

        const responseData = await response.json();
        if (response.ok) {
          alert("Account deleted successfully.");
          // Sign out the user locally after account deletion
          const { error: signOutError } = await supabaseClient.auth.signOut();
          if (signOutError) {
            console.error("Error signing out:", signOutError.message);
            alert("Your account was deleted, but an issue occurred during logout.");
          }
          navigate("/"); // Redirect to home page after successful deletion
        } else {
          alert(`Error: ${responseData.error}`);
        }
      } else {
        alert("You need to be logged in to delete your account.");
      }
    } catch (error) {
      console.error("Deletion Error:", error.message);
      alert("An error occurred while deleting your account. Please try again.");
    }
  };

  return (
    <div className="profile-page">
      <h1>My Profile</h1>
      <div
        className="profile-image-container"
        // onMouseEnter={() => setImageSelectorOpen(true)}
        // onMouseLeave={() => setImageSelectorOpen(false)}
      >
        <img src={profileImage} alt="Profile" className="profile-image" />
        {
          <button className="edit-icon" onClick={() => setImageSelectorOpen((prev) => !prev)}>
            ✏️
          </button>
        }
      </div>
      {isImageSelectorOpen && (
        <div className="image-selector">
          <h3>Select a Profile Image</h3>
          <div className="image-options">
            {availableImages.map((image, index) => (
              <img
                key={index}
                src={image}
                alt={`Option ${index + 1}`}
                className="image-option"
                onClick={() => handleImageChange(image)}
              />
            ))}
          </div>
        </div>
      )}
      <button className="logout-btn" onClick={handleLogout}>
        Log Out
      </button>
      <button className="delete-btn" onClick={handleDelete}>
        Delete your account
      </button>
    </div>
  );
};

export default ProfilePage;
