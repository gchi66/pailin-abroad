import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import useSwipe from "../hooks/useSwipe";
import "../Styles/Onboarding.css";

const Onboarding = () => {
  const [step, setStep] = useState(0);
  const [username, setUsername] = useState("");
  const [selectedAvatar, setSelectedAvatar] = useState("");
  const [passwords, setPasswords] = useState({
    newPassword: "",
    confirmPassword: ""
  });
  const [showPasswords, setShowPasswords] = useState({
    newPassword: false,
    confirmPassword: false
  });
  const [isLoading, setIsLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [error, setError] = useState("");
  const [skipPasswordStep, setSkipPasswordStep] = useState(false);
  const [hasSyncedUser, setHasSyncedUser] = useState(false);
  const [syncingUser, setSyncingUser] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [preferPngAvatars, setPreferPngAvatars] = useState(false);
  const navigate = useNavigate();
  const { ui: uiLang, setUi: setUiLang } = useUiLang();
  const isDevPreview =
    process.env.NODE_ENV === "development" &&
    typeof window !== "undefined" &&
    window.location.search.includes("previewOnboarding=1");

  const passwordValue = passwords.newPassword;
  const confirmPasswordValue = passwords.confirmPassword;
  const meetsLength = passwordValue.length >= 8;
  const meetsNumberOrSymbol = /[\d!@#$%^&*(),.?":{}|<>]/.test(passwordValue);
  const meetsUppercase = /[A-Z]/.test(passwordValue);
  const allPasswordRequirementsMet = meetsLength && meetsNumberOrSymbol && meetsUppercase;
  const passwordsMatch =
    passwordValue.length > 0 &&
    confirmPasswordValue.length > 0 &&
    passwordValue === confirmPasswordValue;
  const shouldShowMismatch =
    confirmPasswordValue.length > 0 &&
    passwordValue.length > 0 &&
    passwordValue !== confirmPasswordValue;
  const canProceedFromPassword = isDevPreview || (allPasswordRequirementsMet && passwordsMatch);
  const canProceedProfile = username.trim() && selectedAvatar;
  const isNextDisabled =
    isLoading ||
    (step === 1 && !canProceedFromPassword) ||
    (step === 2 && !canProceedProfile);

  const ensureUserRecord = useCallback(async (session) => {
    if (isDevPreview || hasSyncedUser || !session?.access_token) {
      return;
    }

    setSyncingUser(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/confirm-email`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ access_token: session.access_token })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to sync account record.");
      }

      setHasSyncedUser(true);
    } catch (syncError) {
      console.error("Error syncing user record:", syncError);
      throw syncError;
    } finally {
      setSyncingUser(false);
    }
  }, [hasSyncedUser, isDevPreview]);

  // Fetch user profile and determine starting step
  useEffect(() => {
    if (isDevPreview) {
      setSkipPasswordStep(false);
      setStep(0);
      setLoadingProfile(false);
      return;
    }

    const fetchUserProfile = async () => {
      try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();

        if (sessionError || !session) {
          console.error("No session found:", sessionError);
          navigate("/"); // Redirect to home if no user
          return;
        }

        try {
          await ensureUserRecord(session);
          setError("");
        } catch (syncErr) {
          setError(syncErr.message || "Unable to verify your account. Please refresh the page.");
          setLoadingProfile(false);
          return;
        }

        const provider = session.user?.app_metadata?.provider;
        const isOAuthUser = provider && provider !== "email";

        // Fetch user profile from database
        const { data: profile, error: profileError } = await supabaseClient
          .from("users")
          .select("is_paid, is_verified, onboarding_completed, username, avatar_image")
          .eq("id", session.user.id)
          .single();

        if (profileError) {
          console.error("Error fetching profile:", profileError);
          // Profile doesn't exist yet, this is OK for new users
          setSkipPasswordStep(Boolean(isOAuthUser));
          setStep(0);
          setLoadingProfile(false);
          return;
        }

        // Edge case 1: If user already completed onboarding, redirect to My Pathway
        if (profile?.onboarding_completed) {
          navigate("/pathway");
          return;
        }

        // Edge case 2: Check if email is verified (from Supabase auth, not custom field)
        const isEmailVerified = session.user.email_confirmed_at !== null;

        if (!isEmailVerified) {
          navigate("/verify-email");
          return;
        }

        // Update is_verified in database if email is verified but DB field is false
        if (isEmailVerified && !profile?.is_verified) {
          await supabaseClient
            .from("users")
            .update({ is_verified: true })
            .eq("id", session.user.id);

        }

        // Determine if we should skip password step
        const shouldSkipPassword = profile?.is_paid === true || Boolean(isOAuthUser);
        setSkipPasswordStep(shouldSkipPassword);

        // Set starting step based on user status
        setStep(0);

        setLoadingProfile(false);
      } catch (err) {
        console.error("Error in fetchUserProfile:", err);
        setLoadingProfile(false);
      }
    };

    fetchUserProfile();
  }, [ensureUserRecord, isDevPreview, navigate]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 480px)");
    const update = (event) => setIsMobile(event.matches);
    setIsMobile(mq.matches);
    if (mq.addEventListener) {
      mq.addEventListener("change", update);
    } else {
      mq.addListener(update);
    }
    return () => {
      if (mq.removeEventListener) {
        mq.removeEventListener("change", update);
      } else {
        mq.removeListener(update);
      }
    };
  }, []);

  useEffect(() => {
    const ua = navigator.userAgent || "";
    const isIOS = /iPad|iPhone|iPod/.test(ua);
    setPreferPngAvatars(isIOS);
  }, []);

  // UI translations
  const uiText = {
    // Welcome Step (Step 0)
    welcomeTitle: t("onboarding.welcomeTitle", uiLang),
    welcomeSubtitle: t("onboarding.welcomeSubtitle", uiLang),
    welcomeDescription: t("onboarding.welcomeDescription", uiLang),

    // Password Step (Step 1)
    passwordTitle: t("onboarding.passwordTitle", uiLang),
    emailLabel: t("onboarding.emailLabel", uiLang),
    newPassword: t("onboarding.newPassword", uiLang),
    confirmPassword: t("onboarding.confirmPassword", uiLang),
    passwordRule1: t("onboarding.passwordRule1", uiLang),
    passwordRule2: t("onboarding.passwordRule2", uiLang),
    passwordRule3: t("onboarding.passwordRule3", uiLang),
    passwordMismatch: t("onboarding.passwordMismatch", uiLang),
    setPassword: t("onboarding.setPassword", uiLang),

    // Username & Avatar Step (Step 2)
    whatToCallYou: t("onboarding.whatToCallYou", uiLang),
    firstNameLabel: t("onboarding.firstNameLabel", uiLang),
    chooseAvatar: t("onboarding.chooseAvatar", uiLang),

    // Benefits Step (Step 3)
    benefitsTitle: t("onboarding.benefitsTitle", uiLang),
    benefit1: t("onboarding.benefit1", uiLang),
    benefit2: t("onboarding.benefit2", uiLang),
    benefit3: t("onboarding.benefit3", uiLang),
    benefit4: t("onboarding.benefit4", uiLang),
    benefit5: t("onboarding.benefit5", uiLang),
    benefit6: t("onboarding.benefit6", uiLang),

    // Confirmation Step (Step 4)
    confirmationTitle: t("onboarding.confirmationTitle", uiLang),
    confirmationSubtitle: t("onboarding.confirmationSubtitle", uiLang),
    confirmationCta: t("onboarding.confirmationCta", uiLang),
    getStarted: t("onboarding.getStarted", uiLang),

    // Navigation
    back: t("onboarding.back", uiLang),
    next: t("onboarding.next", uiLang),

    // Avatar labels for accessibility/tooltips
    avatar1: t("onboarding.avatar1", uiLang),
    avatar2: t("onboarding.avatar2", uiLang),
    avatar3: t("onboarding.avatar3", uiLang),
    avatar4: t("onboarding.avatar4", uiLang),
    avatar5: t("onboarding.avatar5", uiLang),
    avatar6: t("onboarding.avatar6", uiLang),
    avatar7: t("onboarding.avatar7", uiLang),
    avatar8: t("onboarding.avatar8", uiLang)
  };

  const nextStep = () => {
    // Handle step transitions with password skip logic
    if (step === 0) {
      // From welcome, go to password (step 1) or username (step 2) if skipping
      setStep(skipPasswordStep ? 2 : 1);
    } else if (step === 1) {
      // From password, trigger password creation before advancing
      handleSetPassword();
    } else if (step === 2) {
      // From username/avatar, save profile before advancing
      handleCompleteProfile();
    } else if (step === 3) {
      // From benefits, go to confirmation (step 4)
      setStep(4);
    } else if (step === 4) {
      // Complete button clicked - mark onboarding completed and redirect
      handleFinishOnboarding();
    }
  };

  const prevStep = () => {
    // Handle backwards navigation with password skip logic
    if (step === 2 && skipPasswordStep) {
      // If on username and skipped password, go back to welcome (step 0)
      setStep(0);
    } else if (step > 0) {
      setStep(step - 1);
    }
  };

  const { onTouchStart, onTouchMove, onTouchEnd } = useSwipe({
    onSwipeLeft: () => {
      if (step >= 4 || isNextDisabled) return;
      nextStep();
    },
    onSwipeRight: () => {
      if (step <= 0) return;
      prevStep();
    },
    threshold: 70,
  });

  // Finish onboarding - mark onboarding_completed for all users
  const handleFinishOnboarding = async () => {
    if (isDevPreview) {
      setError("");
      navigate("/pathway");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const { data: { user }, error: userError } = await supabaseClient.auth.getUser();

      if (userError || !user) {
        throw new Error("User not found");
      }

      // Update onboarding_completed and unlock paid access for testing
      const { error: updateError } = await supabaseClient
        .from("users")
        .update({ onboarding_completed: true, is_paid: true })
        .eq("id", user.id);

      if (updateError) {
        throw new Error(updateError.message);
      }

      navigate("/pathway");
    } catch (err) {
      console.error("Error completing onboarding:", err);
      setError(err.message || "Failed to complete onboarding");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordChange = (field, value) => {
    setPasswords(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const togglePasswordVisibility = (field) => {
    setShowPasswords(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
  };

  const handleSetPassword = async () => {
    // Clear previous errors upfront
    setError("");

    if (isLoading) {
      return;
    }

    if (isDevPreview) {
      setStep(2);
      return;
    }

    // Validation is handled prior to calling the API.
    if (!allPasswordRequirementsMet) {
      setError("Please meet all password requirements.");
      return;
    }

    if (!passwordsMatch) {
      setError(uiText.passwordMismatch);
      return;
    }

    setIsLoading(true);

    try {
      // Get current session to get access token
      const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();

      if (sessionError || !session) {
        throw new Error("You must be logged in to set your password. Please click the email confirmation link again.");
      }

      // Call the set password API for onboarding
      const response = await fetch(`${API_BASE_URL}/api/set-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          password: passwords.newPassword
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Password setup failed");
      }

      // If a fresh session is provided, update the Supabase client
      if (data.session && data.session.access_token) {
        await supabaseClient.auth.setSession({
          access_token: data.session.access_token,
          refresh_token: data.session.refresh_token
        });
      }

      // If password set successfully, move to next step
      setStep(2);
    } catch (error) {
      console.error("Signup Error:", error);
      setError(error.message || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  // Available avatars for selection
  const avatarOptions = [
    { webp: "/images/characters/avatar_1.webp", png: "/images/characters/avatar_1.png", name: "avatar1" },
    { webp: "/images/characters/avatar_2.webp", png: "/images/characters/avatar_2.png", name: "avatar2" },
    { webp: "/images/characters/avatar_3.webp", png: "/images/characters/avatar_3.png", name: "avatar3" },
    { webp: "/images/characters/avatar_4.webp", png: "/images/characters/avatar_4.png", name: "avatar4" },
    { webp: "/images/characters/avatar_5.webp", png: "/images/characters/avatar_5.png", name: "avatar5" },
    { webp: "/images/characters/avatar_6.webp", png: "/images/characters/avatar_6.png", name: "avatar6" },
    { webp: "/images/characters/avatar_7.webp", png: "/images/characters/avatar_7.png", name: "avatar7" },
    { webp: "/images/characters/avatar_8.webp", png: "/images/characters/avatar_8.png", name: "avatar8" }
  ];

  const handleAvatarSelect = (avatarPath) => {
    setSelectedAvatar(avatarPath);
  };

  const handleCompleteProfile = async () => {
    if (isDevPreview) {
      setError("");
      setStep(3);
      return;
    }

    // Clear previous errors
    setError("");

    // Validation
    if (!username.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (!selectedAvatar) {
      setError("Please select an avatar.");
      return;
    }



    setIsLoading(true);

    try {
      // Get current session to get email
      const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();

      if (sessionError || !session) {
        throw new Error("Authentication required. Please try again.");
      }

      // Update user profile with username and avatar
      const response = await fetch(`${API_BASE_URL}/api/user/profile`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          username: username.trim(),
          avatar_image: selectedAvatar
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to update profile");
      }

      // Profile updated successfully! Move to next step (benefits)
      setStep(3);
    } catch (error) {
      console.error("Profile Update Error:", error);
      setError(error.message || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const renderStepContent = () => {
    // Don't render password step if it should be skipped
    if (step === 1 && skipPasswordStep) {
      return null;
    }

    switch (step) {
      case 0:
        return (
          <div className="onboarding-welcome">
            <div className="onboarding-avatar">
              <img
                src="/images/characters/pailin_blue_circle_right.webp"
                alt="Pailin illustration"
                className="onboarding-avatar-image"
              />
            </div>
            <div className="onboarding-welcome-text">
              <h1 className="onboarding-welcome-title">
                {uiText.welcomeTitle}
              </h1>
              <p className="onboarding-welcome-subtitle">
                {uiText.welcomeSubtitle}
              </p>
              <p className="onboarding-welcome-description">
                {uiText.welcomeDescription}
              </p>
            </div>
          </div>
        );
      case 1:
        return (
          <div className="onboarding-password-setup">
            <h2 className="onboarding-password-title">{uiText.passwordTitle}</h2>

            <div className="onboarding-password-form">
              {/* Error Display */}
              {error && (
                <div className="onboarding-error-message">
                  {error}
                </div>
              )}

              {/* New Password Field */}
              <div className="onboarding-input-group">
                <label className="onboarding-input-label">{uiText.newPassword}</label>
                <div className="onboarding-input-wrapper">
                  <div className="onboarding-input-icon-left">
                    <img
                      src="/images/password-lock.webp"
                      alt=""
                      aria-hidden="true"
                      className="onboarding-input-icon-image"
                    />
                  </div>
                  <input
                    type={showPasswords.newPassword ? "text" : "password"}
                    value={passwords.newPassword}
                    onChange={(e) => handlePasswordChange("newPassword", e.target.value)}
                    className="onboarding-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility("newPassword")}
                    className="onboarding-input-icon-right"
                  >
                    <img
                      src={showPasswords.newPassword ? "/images/hide-password.webp" : "/images/show-password.webp"}
                      alt={showPasswords.newPassword ? "Hide password" : "Show password"}
                      className="onboarding-input-icon-image"
                    />
                  </button>
                </div>
              </div>

              {/* Confirm Password Field */}
              <div className="onboarding-input-group">
                <label className="onboarding-input-label">{uiText.confirmPassword}</label>
                <div className="onboarding-input-wrapper">
                  <div className="onboarding-input-icon-left">
                    <img
                      src="/images/password-lock.webp"
                      alt=""
                      aria-hidden="true"
                      className="onboarding-input-icon-image"
                    />
                  </div>
                  <input
                    type={showPasswords.confirmPassword ? "text" : "password"}
                    value={passwords.confirmPassword}
                    onChange={(e) => handlePasswordChange("confirmPassword", e.target.value)}
                    className="onboarding-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility("confirmPassword")}
                    className="onboarding-input-icon-right"
                  >
                    <img
                      src={showPasswords.confirmPassword ? "/images/hide-password.webp" : "/images/show-password.webp"}
                      alt={showPasswords.confirmPassword ? "Hide password" : "Show password"}
                      className="onboarding-input-icon-image"
                    />
                  </button>
                </div>
                {shouldShowMismatch && (
                  <div className="onboarding-password-mismatch" role="alert">
                    {uiText.passwordMismatch}
                  </div>
                )}
              </div>

              {/* Password Rules */}
              <div className="onboarding-password-rules">
                <div className="onboarding-password-rule">
                  <img
                    src={meetsLength ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsLength ? "✓ Length requirement met" : "Length requirement not met"}
                    className={`onboarding-rule-icon ${meetsLength ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsLength ? "met" : ""}`}>
                    {uiText.passwordRule1}
                  </span>
                </div>
                <div className="onboarding-password-rule">
                  <img
                    src={meetsNumberOrSymbol ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsNumberOrSymbol ? "✓ Number or symbol requirement met" : "Number or symbol requirement not met"}
                    className={`onboarding-rule-icon ${meetsNumberOrSymbol ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsNumberOrSymbol ? "met" : ""}`}>
                    {uiText.passwordRule2}
                  </span>
                </div>
                <div className="onboarding-password-rule">
                  <img
                    src={meetsUppercase ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsUppercase ? "✓ Uppercase letter requirement met" : "Uppercase letter requirement not met"}
                    className={`onboarding-rule-icon ${meetsUppercase ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsUppercase ? "met" : ""}`}>
                    {uiText.passwordRule3}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      case 2:
        return (
          <div className="onboarding-username-avatar">
            {/* Error Display */}
            {error && (
              <div className="onboarding-error-message">
                {error}
              </div>
            )}

            {/* Username Section */}
            <div className="onboarding-section">
              <h2 className="onboarding-section-title">{uiText.whatToCallYou}</h2>
              <div className="onboarding-username-form">
                <div className="onboarding-input-group">
                  <label className="onboarding-input-label">{uiText.firstNameLabel}</label>
                  <div className="onboarding-input-wrapper-simple">
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="onboarding-username-input"
                      placeholder="Enter your name"
                    />
                  </div>
                </div>
              </div>
              </div>

              {/* Avatar Selection Section */}
              <div className="onboarding-section">
                <h2 className="onboarding-section-title">{uiText.chooseAvatar}</h2>
              <div className="onboarding-avatar-grid">
                {avatarOptions.map((avatar, index) => {
                  const selectedPath = preferPngAvatars ? avatar.png : avatar.webp;
                  return (
                  <div
                    key={index}
                    className={`onboarding-avatar-option ${selectedAvatar === selectedPath ? 'selected' : ''}`}
                    onClick={() => handleAvatarSelect(selectedPath)}
                  >
                    {preferPngAvatars ? (
                      <img
                        src={avatar.png}
                        alt={uiText[avatar.name]}
                        title={uiText[avatar.name]}
                        className="onboarding-avatar-image"
                        loading="lazy"
                      />
                    ) : (
                      <picture>
                        <source srcSet={avatar.webp} type="image/webp" />
                        <img
                          src={avatar.png}
                          alt={uiText[avatar.name]}
                          title={uiText[avatar.name]}
                          className="onboarding-avatar-image"
                          loading="lazy"
                        />
                      </picture>
                    )}
                  </div>
                );
                })}
              </div>
            </div>
          </div>
        );
      case 3: {
        const benefits = [
          uiText.benefit1,
          uiText.benefit2,
          uiText.benefit3,
          uiText.benefit4,
          uiText.benefit5,
          uiText.benefit6
        ];
        return (
          <div className="onboarding-benefits">
            <h2 className="onboarding-section-title">{uiText.benefitsTitle}</h2>
            <div className="onboarding-benefits-list">
              {benefits.map((benefit, index) => (
                <div className="onboarding-benefit-item" key={`benefit-${index}`}>
                  <span className="onboarding-benefit-check">
                    <img
                      src="/images/blue-checkmark.webp"
                      alt=""
                      aria-hidden="true"
                      className="onboarding-benefit-check-icon"
                    />
                  </span>
                  <span className="onboarding-benefit-text">{benefit}</span>
                </div>
              ))}
            </div>
          </div>
        );
      }
      case 4:
        return (
          <div className="onboarding-confirmation">
            <h2 className="onboarding-confirmation-title">{uiText.confirmationTitle}</h2>
            <p className="onboarding-confirmation-subtitle">
              {uiText.confirmationSubtitle}
            </p>
            <p className="onboarding-confirmation-subtitle">
              {uiText.confirmationCta}
            </p>
            <button
              onClick={handleFinishOnboarding}  // ✅ Call the function that completes onboarding
              className="submit-btn onboarding-confirmation-button"
              disabled={isLoading}
            >
              {isLoading ? "Setting up..." : uiText.getStarted}
            </button>
          </div>
        );
      default:
        return null;
    }
  };

  const renderProgressDots = () => {
    const dots = [];
    // Calculate which steps to show
    // If skipPasswordStep, we have: 0 (welcome), 2 (username), 3 (benefits), 4 (confirmation)
    // Map visual dots to actual steps
    const totalVisualDots = skipPasswordStep ? 3 : 4;

    let currentDotIndex;
    if (skipPasswordStep) {
      // Map: step 0→dot 0, step 2→dot 1, step 3→dot 2, step 4→dot 3
      if (step === 0) currentDotIndex = 0;
      else if (step === 2) currentDotIndex = 1;
      else if (step === 3) currentDotIndex = 2;
      else if (step === 4) currentDotIndex = 3;
    } else {
      // Normal: step 0→dot 0, step 1→dot 1, step 2→dot 2, step 3→dot 3, step 4 (no dot, just finish)
      currentDotIndex = step;
    }

    for (let i = 0; i < totalVisualDots; i++) {
      dots.push(
        <div
          key={i}
          className={`onboarding-dot ${i === currentDotIndex ? 'active' : ''}`}
        />
      );
    }
    return dots;
  };

  // Show loading state while fetching profile
  if (loadingProfile || syncingUser) {
    return (
      <div className="onboarding-main">
        <div className="onboarding-container">
          <div className="onboarding-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
            <div style={{ textAlign: 'center' }}>
              <p>{syncingUser ? "Preparing your account..." : "Loading..."}</p>
              {error && (
                <p className="onboarding-error-message" style={{ marginTop: '1rem' }}>
                  {error}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding-main">
      <div className="onboarding-mobile-logo">
        <img
          src="/images/full-logo.webp"
          alt="Pailin Abroad Logo"
          className="onboarding-mobile-logo-image"
        />
      </div>
      <div className="onboarding-container">
        {/* Top Navigation - now just language toggle */}
        <nav className="onboarding-nav">
          <div className="onboarding-nav-logo">
            <img
              src="/images/full-logo.webp"
              alt="Pailin Abroad Logo"
              className="onboarding-nav-logo-image"
            />
          </div>
          <div className="onboarding-language-toggle">
            <button
              className={`onboarding-lang-btn ${uiLang === 'en' ? 'active' : ''}`}
              onClick={() => setUiLang('en')}
            >
              EN
            </button>
            <span className="onboarding-lang-separator">|</span>
            <button
              className={`onboarding-lang-btn ${uiLang === 'th' ? 'active' : ''}`}
              onClick={() => setUiLang('th')}
            >
              TH
            </button>
          </div>
        </nav>

        {/* Step Content */}
        <div
          className="onboarding-content"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          {isMobile ? (
            <div className="onboarding-card-wrapper">
              <div className="onboarding-card-header-mobile">
                <div className="onboarding-card-header-spacer" aria-hidden="true" />
                <div className="onboarding-card-lang-toggle">
                  <button
                    className={`onboarding-lang-btn ${uiLang === 'en' ? 'active' : ''}`}
                    onClick={() => setUiLang('en')}
                    aria-label="Switch to English"
                  >
                    EN
                  </button>
                  <span className="onboarding-lang-separator">|</span>
                  <button
                    className={`onboarding-lang-btn ${uiLang === 'th' ? 'active' : ''}`}
                    onClick={() => setUiLang('th')}
                    aria-label="Switch to Thai"
                  >
                    TH
                  </button>
                </div>
              </div>
              <div className="onboarding-card-body">
                {renderStepContent()}
              </div>
              {step < 4 && (
                <div className="onboarding-mobile-progress">
                  {renderProgressDots()}
                </div>
              )}
              <div className="onboarding-mobile-footer">
                <div className="onboarding-mobile-footer-left">
                  {step > 0 ? (
                    <button
                      className="onboarding-back-btn"
                      onClick={prevStep}
                    >
                      ← {uiText.back}
                    </button>
                  ) : (
                    <span className="onboarding-footer-spacer" aria-hidden="true" />
                  )}
                </div>
                <div className="onboarding-mobile-footer-right">
                  {step < 4 && (
                    <button
                      className="onboarding-next-btn onboarding-mobile-next"
                      onClick={nextStep}
                      disabled={isNextDisabled}
                    >
                      {step === 1 && isLoading ? "..." : `${uiText.next} →`}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            renderStepContent()
          )}
        </div>

        {/* Bottom Navigation */}
        {!isMobile && (
          <div className="onboarding-bottom">
            {step < 4 && (
              <div className="onboarding-progress">
                {renderProgressDots()}
              </div>
            )}
            {step < 4 && (
              <div className="onboarding-navigation">
                {step > 0 && (
                  <button
                    className="onboarding-back-btn"
                    onClick={prevStep}
                  >
                    ← {uiText.back}
                  </button>
                )}
                <button
                  className="onboarding-next-btn"
                  onClick={nextStep}
                  disabled={isNextDisabled}
                >
                  {step === 1 && isLoading ? "..." : `${uiText.next} →`}
                </button>
              </div>
            )}
            {step === 4 && (
              <div className="onboarding-navigation">
                <button
                  className="onboarding-back-btn"
                  onClick={prevStep}
                >
                  ← {uiText.back}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Onboarding;
