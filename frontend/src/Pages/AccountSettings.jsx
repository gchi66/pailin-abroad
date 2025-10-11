import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import SubscriptionBilling from "../Components/SubscriptionBilling";
import "../Styles/AccountSettings.css";

const AccountSettings = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("profile");
  const [firstName, setFirstName] = useState("John");
  const [isEditingFirstName, setIsEditingFirstName] = useState(false);
  const [showManageAccount, setShowManageAccount] = useState(false);
  const [profileImage, setProfileImage] = useState("/images/characters/pailin-blue-right.png");

  const handleSaveFirstName = () => {
    // TODO: Save to backend
    setIsEditingFirstName(false);
  };

  const handleChangeEmail = () => {
    // TODO: Implement email change
    console.log("Change email clicked");
  };

  const handleChangePassword = () => {
    // TODO: Implement password change
    console.log("Change password clicked");
  };

  const handleLogout = async () => {
    try {
      await supabaseClient.auth.signOut();
      navigate("/");
    } catch (error) {
      console.error("Logout Error:", error.message);
    }
  };

  const handleDeleteAccount = async () => {
    const confirmation = window.confirm(
      "Are you sure you want to delete your account? This action cannot be undone."
    );
    if (!confirmation) return;

    try {
      const { data: { session } } = await supabaseClient.auth.getSession();
      if (session?.access_token) {
        const response = await fetch("http://127.0.0.1:5000/api/delete_account", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: session.access_token }),
        });

        if (response.ok) {
          alert("Account deleted successfully.");
          await supabaseClient.auth.signOut();
          navigate("/");
        } else {
          const data = await response.json();
          alert(`Error: ${data.error}`);
        }
      }
    } catch (error) {
      console.error("Deletion Error:", error.message);
      alert("An error occurred while deleting your account. Please try again.");
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "profile":
        return (
          <div className="account-profile-section">
            <h3 className="account-section-title">MY PROFILE</h3>

            {/* Avatar Section */}
            <div className="account-avatar-container">
              <div className="account-avatar-wrapper">
                <img
                  src={profileImage}
                  alt="Profile Avatar"
                  className="account-avatar"
                />
                <button className="account-avatar-edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                  </svg>
                </button>
              </div>
            </div>

            {/* Form Fields */}
            <div className="account-form-section">
              {/* First Name Field */}
              <div className="account-field">
                <label className="account-field-label">First Name</label>
                <div className="account-field-row">
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    disabled={!isEditingFirstName}
                    className={`account-input ${!isEditingFirstName ? 'disabled' : ''}`}
                  />
                  {isEditingFirstName ? (
                    <button className="account-btn primary" onClick={handleSaveFirstName}>
                      Save
                    </button>
                  ) : (
                    <button className="account-btn" onClick={() => setIsEditingFirstName(true)}>
                      Edit
                    </button>
                  )}
                </div>
              </div>

              {/* Email Field */}
              <div className="account-field">
                <label className="account-field-label">Email Address</label>
                <div className="account-field-row">
                  <input
                    type="email"
                    value={user?.email || "user@example.com"}
                    disabled
                    className="account-input disabled"
                  />
                  <button className="account-btn" onClick={handleChangeEmail}>
                    Change Email
                  </button>
                </div>
              </div>

              {/* Password Field */}
              <div className="account-field">
                <label className="account-field-label">Password</label>
                <div className="account-field-row">
                  <input
                    type="password"
                    value="••••••••"
                    disabled
                    className="account-input disabled"
                  />
                  <button className="account-btn" onClick={handleChangePassword}>
                    Change Password
                  </button>
                </div>
              </div>
            </div>

            {/* Manage Account Dropdown */}
            <div className="account-manage-section">
              <button
                className="account-manage-toggle"
                onClick={() => setShowManageAccount(!showManageAccount)}
              >
                <span>MANAGE MY ACCOUNT</span>
                <svg
                  className={`account-caret ${showManageAccount ? 'rotated' : ''}`}
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                >
                  <path d="M8 12l-4-4h8l-4 4z"/>
                </svg>
              </button>

              {showManageAccount && (
                <div className="account-manage-content">
                  <button className="account-manage-item" onClick={handleLogout}>
                    Log Out
                  </button>
                  <button className="account-manage-item delete" onClick={handleDeleteAccount}>
                    Delete Account
                  </button>
                </div>
              )}
            </div>
          </div>
        );

      case "billing":
        return (
          <SubscriptionBilling />
        );

      default:
        return null;
    }
  };

  return (
    <main className="pathway-main">
      <div className="pathway-container">
        {/* Header */}
        <div className="account-header">
          <h1 className="account-title">ACCOUNT SETTINGS</h1>
        </div>

        {/* Navigation Tabs */}
        <nav className="pathway-nav">
          <div className="pathway-tabs">
            <button
              className={`pathway-tab ${activeTab === "profile" ? "active" : ""}`}
              onClick={() => setActiveTab("profile")}
            >
              EDIT PROFILE
            </button>
            <button
              className={`pathway-tab ${activeTab === "billing" ? "active" : ""}`}
              onClick={() => setActiveTab("billing")}
            >
              SUBSCRIPTION & BILLING
            </button>
          </div>
        </nav>

        {/* Tab Content */}
        <div className="pathway-content">
          {renderTabContent()}
        </div>
      </div>
    </main>
  );
};

export default AccountSettings;
