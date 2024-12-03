import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import "../Styles/ProfilePage.css";


const ProfilePage = () => {
  const placeholderImage = "/images/Pailin.png";
  const [profileImage, setProfileImage] = useState(placeholderImage);
  const [isImageSelectorOpen, setImageSelectorOpen] = useState(false);
  const navigate = useNavigate();

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
    const { error } = await supabaseClient.auth.signOut();
    if (error) {
      console.error("Error logging out:", error.message);
    } else {
      console.log("User successfully logged out.");
      navigate("/login");
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
      <button className="delete-btn" onClick={handleLogout}>
        Delete your account
      </button>
    </div>
  );
};

export default ProfilePage;
