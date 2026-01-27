import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick, t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import SubscriptionBilling from "../Components/SubscriptionBilling";
import ConfirmPasswordModal from "../Components/ConfirmPasswordModal";
import PasswordResetSentModal from "../Components/PasswordResetSentModal";
import { API_BASE_URL } from "../config/api";
import "../Styles/AccountSettings.css";

const AccountSettings = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const avatarOptions = [
    "/images/characters/avatar_1.webp",
    "/images/characters/avatar_2.webp",
    "/images/characters/avatar_3.webp",
    "/images/characters/avatar_4.webp",
    "/images/characters/avatar_5.webp",
    "/images/characters/avatar_6.webp",
    "/images/characters/avatar_7.webp",
    "/images/characters/avatar_8.webp",
  ];
  const [activeTab, setActiveTab] = useState("profile");
  const [firstName, setFirstName] = useState("John");
  const [isEditingFirstName, setIsEditingFirstName] = useState(false);
  const [showManageAccount, setShowManageAccount] = useState(false);
  const [profileImage, setProfileImage] = useState(avatarOptions[0]);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isPaidMember, setIsPaidMember] = useState(null);
  const [showPasswordConfirmModal, setShowPasswordConfirmModal] = useState(false);
  const [passwordConfirmError, setPasswordConfirmError] = useState("");
  const [isPasswordConfirmLoading, setIsPasswordConfirmLoading] = useState(false);
  const [showPasswordResetSentModal, setShowPasswordResetSentModal] = useState(false);
  const [passwordResetSentMessage, setPasswordResetSentMessage] = useState("");
  const { ui: uiLang } = useUiLang();
  const freePlanBenefits = (copy.freePlanBenefits?.items || []).map((item) => pick(item, uiLang));
  const isGoogleAuth =
    user?.app_metadata?.provider === "google" ||
    user?.app_metadata?.providers?.includes("google");

  const handleSaveFirstName = () => {
    // TODO: Save to backend
    setIsEditingFirstName(false);
  };

  const sendPasswordResetEmail = async () => {
    if (!user?.email) {
      throw new Error(t("authModals.confirmPassword.errors.noEmail", uiLang));
    }

    const response = await fetch(`${API_BASE_URL}/api/forgot-password/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email: user.email }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.error || t("authModals.forgotPassword.errors.resetFail", uiLang));
    }

    return data.message || t("accountSettings.resetEmailSent", uiLang);
  };

  const handleChangePassword = () => {
    setPasswordConfirmError("");
    setShowPasswordConfirmModal(true);
  };

  const handleConfirmPasswordAndSendReset = async (password) => {
    if (!password) {
      setPasswordConfirmError(t("authModals.confirmPassword.errors.missing", uiLang));
      return;
    }
    if (!user?.email) {
      setPasswordConfirmError(t("authModals.confirmPassword.errors.noEmail", uiLang));
      return;
    }

    setIsPasswordConfirmLoading(true);
    setPasswordConfirmError("");

    try {
      const loginResponse = await fetch(`${API_BASE_URL}/api/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: user?.email, password }),
      });
      const loginData = await loginResponse.json();

      if (!loginResponse.ok) {
        throw new Error(loginData?.error || t("accountSettings.incorrectPassword", uiLang));
      }

      const message = await sendPasswordResetEmail();
      const localizedMessage =
        uiLang === "th" ? t("authModals.resetSent.defaultMessage", uiLang) : message;
      setShowPasswordConfirmModal(false);
      setPasswordResetSentMessage(localizedMessage);
      setShowPasswordResetSentModal(true);
    } catch (error) {
      console.error("Password confirmation error:", error.message);
      setPasswordConfirmError(error.message || t("accountSettings.confirmPasswordFail", uiLang));
    } finally {
      setIsPasswordConfirmLoading(false);
    }
  };

  const handleAvatarSelect = (src) => {
    setProfileImage(src);
    setShowAvatarPicker(false);
  };

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 480px)");
    const handleChange = (event) => setIsMobile(event.matches);
    setIsMobile(mq.matches);
    if (mq.addEventListener) {
      mq.addEventListener("change", handleChange);
    } else {
      mq.addListener(handleChange);
    }
    return () => {
      if (mq.removeEventListener) {
        mq.removeEventListener("change", handleChange);
      } else {
        mq.removeListener(handleChange);
      }
    };
  }, []);

  useEffect(() => {
    const fetchPlanStatus = async () => {
      if (!user) {
        setIsPaidMember(null);
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("users")
          .select("is_paid")
          .eq("id", user.id)
          .single();

        if (error) {
          throw error;
        }

        setIsPaidMember(data?.is_paid ?? null);
      } catch (planError) {
        console.error("Error fetching plan status:", planError.message || planError);
        setIsPaidMember(null);
      }
    };

    fetchPlanStatus();
  }, [user]);

  const handleLogout = async () => {
    try {
      await supabaseClient.auth.signOut();
      navigate("/");
    } catch (error) {
      console.error("Logout Error:", error.message);
    }
  };

  const handleDeleteAccount = async () => {
    const confirmation = window.confirm(t("accountSettings.deleteConfirm", uiLang));
    if (!confirmation) return;

    try {
      const { data: { session } } = await supabaseClient.auth.getSession();
      if (session?.access_token) {
        const response = await fetch(`${API_BASE_URL}/api/delete_account`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: session.access_token }),
        });

        if (response.ok) {
          alert(t("accountSettings.deleteSuccess", uiLang));
          await supabaseClient.auth.signOut();
          navigate("/");
        } else {
          const data = await response.json();
          alert(`Error: ${data.error}`);
        }
      }
    } catch (error) {
      console.error("Deletion Error:", error.message);
      alert(t("accountSettings.deleteError", uiLang));
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "profile":
        return (
          <div className="account-profile-section">
            <h3 className="account-section-title">{t("accountSettings.myProfileTitle", uiLang)}</h3>

            {/* Avatar Section */}
            <div className="account-field">
              <label className="account-field-label">{t("accountSettings.avatarLabel", uiLang)}</label>
              <div className="account-avatar-row">
                <div className="account-avatar-wrapper">
                  <img
                    src={profileImage}
                    alt={t("accountSettings.profileAvatarAlt", uiLang)}
                    className="account-avatar"
                  />
                  <button
                    className="account-avatar-edit"
                    onClick={() => setShowAvatarPicker(!showAvatarPicker)}
                    aria-label={t("accountSettings.changeAvatarAria", uiLang)}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                    </svg>
                  </button>
                </div>

                {showAvatarPicker && (
                  <div className="account-avatar-grid two-rows">
                    {avatarOptions.map((avatar) => (
                      <button
                        key={avatar}
                        className="account-avatar-option"
                        onClick={() => handleAvatarSelect(avatar)}
                        aria-label={t("accountSettings.chooseAvatarAria", uiLang)}
                      >
                        <img src={avatar} alt={t("accountSettings.selectableAvatarAlt", uiLang)} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Form Fields */}
            <div className="account-form-section">
              {/* First Name Field */}
              <div className="account-field">
                <label className="account-field-label">{t("accountSettings.firstNameLabel", uiLang)}</label>
                <div className="account-field-row account-field-row--center">
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    disabled={!isEditingFirstName}
                    className={`account-input ${!isEditingFirstName ? 'disabled' : ''}`}
                  />
                  {isEditingFirstName ? (
                    <button className="account-btn primary" onClick={handleSaveFirstName}>
                      {t("accountSettings.save", uiLang)}
                    </button>
                  ) : (
                    <button className="account-btn" onClick={() => setIsEditingFirstName(true)}>
                      {t("accountSettings.edit", uiLang)}
                    </button>
                  )}
                </div>
              </div>

              {/* Email Field */}
              <div className="account-field">
                <label className="account-field-label">{t("accountSettings.emailAddressLabel", uiLang)}</label>
                <div className="account-field-row account-field-row--center">
                  <input
                    type="email"
                    value={user?.email || "user@example.com"}
                    disabled
                    className="account-input disabled"
                  />
                </div>
              </div>

              {!isGoogleAuth && (
                <div className="account-field">
                  <label className="account-field-label">{t("accountSettings.passwordLabel", uiLang)}</label>
                  <div className="account-field-row account-field-row--center">
                    <input
                      type="password"
                      value="••••••••"
                      disabled
                      className="account-input disabled"
                    />
                    <button className="account-btn" onClick={handleChangePassword}>
                      {t("accountSettings.changePassword", uiLang)}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Manage Account Dropdown */}
            <div className="account-manage-section">
              <button
                className="account-manage-toggle"
                onClick={() => setShowManageAccount(!showManageAccount)}
              >
                <span>{t("accountSettings.manageAccount", uiLang)}</span>
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
                    {t("accountSettings.logout", uiLang)}
                  </button>
                  <button className="account-manage-item delete" onClick={handleDeleteAccount}>
                    {t("accountSettings.deleteAccount", uiLang)}
                  </button>
                </div>
              )}
            </div>
          </div>
        );

      case "billing":
        return isMobile && isPaidMember === false ? (
          <div className="account-free-plan-card">
            <div className="account-free-plan-header">
              <span className="account-free-plan-label">{t("accountSettings.currentPlan", uiLang)}</span>
              <span className="account-free-plan-value">{t("accountSettings.freePlan", uiLang)}</span>
            </div>
            <div className="account-free-plan-body">
              <p className="account-free-plan-included">{t("accountSettings.includedInPlan", uiLang)}</p>
              <ul className="account-free-plan-list">
                {freePlanBenefits.map((item) => (
                  <li key={item} className="account-free-plan-item">
                    <img
                      src="/images/blue-checkmark.webp"
                      alt=""
                      aria-hidden="true"
                      className="account-free-plan-check"
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="account-free-plan-footer">
              <p className="account-free-plan-cta-text">
                {t("accountSettings.fullLibraryCta", uiLang)}
              </p>
              <Link to="/membership" className="account-free-plan-btn">
                {t("accountSettings.becomeMember", uiLang)}
              </Link>
            </div>
          </div>
        ) : (
          <SubscriptionBilling />
        );

      default:
        return null;
    }
  };

  return (
    <>
      <main className="account-main">
        <div className="account-container">
          {/* Header */}
          <div className="account-header">
            <h1 className="account-title">{t("accountSettings.title", uiLang)}</h1>
          </div>

          {/* Navigation Tabs */}
          <nav className="pathway-nav">
            <div className="pathway-tabs">
              <button
                className={`pathway-tab ${activeTab === "profile" ? "active" : ""}`}
                onClick={() => setActiveTab("profile")}
              >
                {t("accountSettings.editProfileTab", uiLang)}
              </button>
              <button
                className={`pathway-tab ${activeTab === "billing" ? "active" : ""}`}
                onClick={() => setActiveTab("billing")}
              >
                {t("accountSettings.subscriptionBillingTab", uiLang)}
              </button>
            </div>
          </nav>

          {/* Tab Content */}
          <div className="pathway-content">
            {renderTabContent()}
          </div>
        </div>
      </main>

      <ConfirmPasswordModal
        isOpen={showPasswordConfirmModal}
        onClose={() => setShowPasswordConfirmModal(false)}
        onConfirm={handleConfirmPasswordAndSendReset}
        isLoading={isPasswordConfirmLoading}
        error={passwordConfirmError}
      />
      <PasswordResetSentModal
        isOpen={showPasswordResetSentModal}
        onClose={() => setShowPasswordResetSentModal(false)}
        message={passwordResetSentMessage}
      />
    </>
  );
};

export default AccountSettings;
