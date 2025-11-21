import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
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
  const [userProfile, setUserProfile] = useState(null);
  const [skipPasswordStep, setSkipPasswordStep] = useState(false);
  const navigate = useNavigate();
  const { ui: uiLang, setUi: setUiLang } = useUiLang();
  const withUi = useWithUi();
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

  // Fetch user profile and determine starting step
  useEffect(() => {
    if (isDevPreview) {
      setUserProfile({
        username: "Preview Student",
        avatar_image: "",
        is_verified: true,
        is_paid: false,
        is_active: false
      });
      setSkipPasswordStep(false);
      setStep(0);
      setLoadingProfile(false);
      return;
    }

    const fetchUserProfile = async () => {
      try {
        const { data: { user }, error: userError } = await supabaseClient.auth.getUser();

        if (userError || !user) {
          console.error("No user found:", userError);
          navigate("/"); // Redirect to home if no user
          return;
        }

        // Fetch user profile from database
        const { data: profile, error: profileError } = await supabaseClient
          .from("users")
          .select("is_paid, is_verified, is_active, username, avatar_image")
          .eq("id", user.id)
          .single();

        if (profileError) {
          console.error("Error fetching profile:", profileError);
          // Profile doesn't exist yet, this is OK for new users
          setLoadingProfile(false);
          setStep(0); // Start at welcome step
          return;
        }

        setUserProfile(profile);

        // Edge case 1: If user is already active, redirect to My Pathway
        if (profile?.is_active) {
          console.log("User already active, redirecting to My Pathway");
          navigate("/pathway");
          return;
        }

        // Edge case 2: Check if email is verified (from Supabase auth, not custom field)
        const isEmailVerified = user.email_confirmed_at !== null;

        if (!isEmailVerified) {
          console.log("User email not verified, redirecting to verify email");
          navigate("/verify-email");
          return;
        }

        // Update is_verified in database if email is verified but DB field is false
        if (isEmailVerified && !profile?.is_verified) {
          console.log("Syncing email verification to database...");
          await supabaseClient
            .from("users")
            .update({ is_verified: true })
            .eq("id", user.id);

          // Update local profile state
          setUserProfile(prev => ({ ...prev, is_verified: true }));
        }

        // Determine if we should skip password step
        const shouldSkipPassword = profile?.is_paid === true;
        setSkipPasswordStep(shouldSkipPassword);

        // Set starting step based on user status
        if (shouldSkipPassword) {
          setStep(2); // Skip welcome and password, start at username/avatar
          console.log("Paid user - skipping password step, starting at step 2");
        } else {
          setStep(0); // Start at welcome for regular users
          console.log("Regular user - starting at welcome step");
        }

        setLoadingProfile(false);
      } catch (err) {
        console.error("Error in fetchUserProfile:", err);
        setLoadingProfile(false);
      }
    };

    fetchUserProfile();
  }, [isDevPreview, navigate]);

  // Helper function to pick the right language content
  const pickLang = (en, th) => {
    if (uiLang === "th") {
      return th || en; // fallback to English if Thai is not available
    }
    return en || th; // fallback to Thai if English is not available
  };

  // UI translations
  const uiText = {
    // Welcome Step (Step 0)
    welcomeTitle: pickLang("Welcome to Pailin Abroad!", "ยินดีต้อนรับสู่ Pailin Abroad!"),
    welcomeSubtitle: pickLang("Hi, I'm Pailin! I'm so excited to be your guide on this English journey.", "สวัสดีค่ะ ฉันไผลิน! ฉันตื่นเต้นมากที่จะเป็นไกด์ในการเรียนภาษาอังกฤษของคุณ"),
    welcomeDescription: pickLang("In a few quick steps, we'll get you ready to explore my world and the language I use every day.", "ในไม่กี่ขั้นตอนง่ายๆ เราจะเตรียมคุณให้พร้อมสำหรับการสำรวจโลกของฉันและภาษาที่ฉันใช้ทุกวัน"),

    // Password Step (Step 1)
    passwordTitle: pickLang("Let's set up your password", "มาตั้งค่ารหัสผ่านของคุณกันเถอะ"),
    emailLabel: pickLang("Email address", "ที่อยู่อีเมล"),
    newPassword: pickLang("New password", "รหัสผ่านใหม่"),
    confirmPassword: pickLang("Confirm password", "ยืนยันรหัสผ่าน"),
    passwordRule1: pickLang("At least 8 characters", "อย่างน้อย 8 ตัวอักษร"),
    passwordRule2: pickLang("At least 1 number or special character", "อย่างน้อย 1 ตัวเลขหรือสัญลักษณ์พิเศษ"),
    passwordRule3: pickLang("At least 1 uppercase letter", "อย่างน้อย 1 ตัวอักษรพิมพ์ใหญ่"),
    setPassword: pickLang("CREATE ACCOUNT", "สร้างบัญชี"),

    // Username & Avatar Step (Step 2)
    whatToCallYou: pickLang("What should we call you?", "เราควรเรียกคุณว่าอะไรดี?"),
    firstNameLabel: pickLang("First Name or Nickname", "ชื่อจริงหรือชื่อเล่น"),
    chooseAvatar: pickLang("Choose an avatar", "เลือกรูปโปรไฟล์"),

    // Benefits Step (Step 3)
    benefitsTitle: pickLang("What's included in my free account?", "บัญชีฟรีของฉันมีอะไรบ้าง?"),
    benefit1: pickLang("Access to the 1st lesson of each level – 12 lessons total!", "เข้าถึงบทเรียนแรกของแต่ละระดับ – รวม 12 บทเรียน!"),
    benefit2: pickLang("Leave comments on free lessons and get feedback from us!", "แสดงความคิดเห็นในบทเรียนฟรีและได้รับคำตอบจากเรา!"),
    benefit3: pickLang("Partial access to our Resource pages, which include:", "เข้าถึงหน้าแหล่งข้อมูลบางส่วน ซึ่งรวมถึง:"),
    resource1: pickLang("Grammar exercise bank", "คลังแบบฝึกหัดไวยากรณ์"),
    resource2: pickLang("Common mistakes made by Thai speakers", "ข้อผิดพลาดที่คนไทยมักทำ"),
    resource3: pickLang("Useful phrases & phrasal verbs", "วลีที่มีประโยชน์และ phrasal verbs"),
    resource4: pickLang("American culture notes", "บันทึกวัฒนธรรมอเมริกัน"),
    resource5: pickLang("Reference pages to supplement your English learning", "หน้าอ้างอิงเพื่อเสริมการเรียนภาษาอังกฤษ"),

    // Confirmation Step (Step 4)
    confirmationTitle: pickLang("You're all set!", "เสร็จเรียบร้อยแล้ว!"),
    confirmationSubtitle: pickLang("Your profile is complete and you're officially part of the Pailin Abroad community. Get ready to learn!", "โปรไฟล์ของคุณสมบูรณ์แล้วและคุณได้เป็นส่วนหนึ่งของชุมชน Pailin Abroad อย่างเป็นทางการ เตรียมตัวเรียนกันเถอะ!"),
    getStarted: pickLang("GET STARTED!", "เริ่มเรียนเลย!"),

    // Navigation
    back: pickLang("BACK", "ย้อนกลับ"),
    next: pickLang("NEXT", "ถัดไป"),

    // Character names for tooltips
    pailin: pickLang("Pailin", "ไผลิน"),
    markDad: pickLang("Mark (Dad)", "มาร์ค (พ่อ)"),
    sylvieMom: pickLang("Sylvie (Mom)", "ซิลวี่ (แม่)"),
    tylerBrother: pickLang("Tyler (Brother)", "ไทเลอร์ (พี่ชาย)"),
    emilySister: pickLang("Emily (Sister)", "เอมิลี่ (น้องสาว)"),
    lukeCoworker: pickLang("Luke (Coworker)", "ลุค (เพื่อนร่วมงาน)"),
    chloeFriend: pickLang("Chloe (Friend)", "โคลอี้ (เพื่อน)"),
    thaiDad: pickLang("Thai Dad", "พ่อไทย")
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
      // Complete button clicked - set is_active and redirect
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
      console.log(`Moving back to step ${step - 1}`);
    }
  };

  // Finish onboarding - set is_active = true for all users
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

      // Update is_active and is_verified to true
      const { error: updateError } = await supabaseClient
        .from("users")
        .update({ is_active: true })
        .eq("id", user.id);

      if (updateError) {
        throw new Error(updateError.message);
      }

      console.log("Onboarding completed, user is now active");
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
      setError("Passwords don't match.");
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
    { path: "/images/characters/pailin-blue-left.png", name: "pailin" },
    { path: "/images/characters/mark-dad-blue-left.png", name: "markDad" },
    { path: "/images/characters/sylvie-mom-blue-left.png", name: "sylvieMom" },
    { path: "/images/characters/tyler-brother-blue-left.png", name: "tylerBrother" },
    { path: "/images/characters/emily-sister-blue-left.png", name: "emilySister" },
    { path: "/images/characters/luke-coworker-blue-left.png", name: "lukeCoworker" },
    { path: "/images/characters/chloe-friend-blue-left.png", name: "chloeFriend" },
    { path: "/images/characters/pailin-thai-dad-blue-left.png", name: "thaiDad" }
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
            <div className="onboarding-welcome-content">
              <div className="onboarding-welcome-left">
                <div className="onboarding-avatar">
                  <img
                    src="/images/characters/pailin-blue-left.png"
                    alt="Pailin"
                    className="onboarding-avatar-image"
                  />
                </div>
              </div>
              <div className="onboarding-welcome-right">
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
                    Passwords don't match
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
                {avatarOptions.map((avatar, index) => (
                  <div
                    key={index}
                    className={`onboarding-avatar-option ${selectedAvatar === avatar.path ? 'selected' : ''}`}
                    onClick={() => handleAvatarSelect(avatar.path)}
                  >
                    <img
                      src={avatar.path}
                      alt={uiText[avatar.name]}
                      title={uiText[avatar.name]}
                      className="onboarding-avatar-image"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      case 3: {
        const resourceBenefits = [
          uiText.resource1,
          uiText.resource2,
          uiText.resource3,
          uiText.resource4,
          uiText.resource5
        ];
        const coreBenefits = [uiText.benefit1, uiText.benefit2, uiText.benefit3];
        return (
          <div className="onboarding-benefits">
            <h2 className="onboarding-section-title">{uiText.benefitsTitle}</h2>
            <div className="onboarding-benefits-list">
              {[...coreBenefits, ...resourceBenefits].map((benefit, index) => (
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
            <button
              onClick={handleFinishOnboarding}  // ✅ Call the function that sets is_active
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
  if (loadingProfile) {
    return (
      <div className="onboarding-main">
        <div className="onboarding-container">
          <div className="onboarding-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
            <p>Loading...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding-main">
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
        <div className="onboarding-content">
          {renderStepContent()}
        </div>

        {/* Bottom Navigation */}
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
      </div>
    </div>
  );
};

export default Onboarding;
