import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import supabaseClient from "../supabaseClient";
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
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { ui: uiLang, setUi: setUiLang } = useUiLang();
  const withUi = useWithUi();

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
    passwordTitle: pickLang("Let's set up your account", "มาตั้งค่าบัญชีของคุณกันเถอะ"),
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
    if (step < 4) {
      setStep(step + 1);
      console.log(`Moving to step ${step + 1}`);
    } else {
      // Complete button clicked - redirect to My Pathway
      console.log("Onboarding completed, redirecting to My Pathway");
      navigate("/pathway");
    }
  };

  const prevStep = () => {
    if (step > 0) {
      setStep(step - 1);
      console.log(`Moving back to step ${step - 1}`);
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
    // Clear previous errors
    setError("");

    // Validation
    if (!passwords.newPassword || !passwords.confirmPassword) {
      setError("Please fill in all fields.");
      return;
    }

    if (passwords.newPassword !== passwords.confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    if (passwords.newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
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
      const response = await fetch("http://127.0.0.1:5000/api/set-password", {
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
      const response = await fetch("http://127.0.0.1:5000/api/user/profile", {
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
                    🔒
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
                    {showPasswords.newPassword ? "🙈" : "👁️"}
                  </button>
                </div>
              </div>

              {/* Confirm Password Field */}
              <div className="onboarding-input-group">
                <label className="onboarding-input-label">{uiText.confirmPassword}</label>
                <div className="onboarding-input-wrapper">
                  <div className="onboarding-input-icon-left">
                    🔒
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
                    {showPasswords.confirmPassword ? "🙈" : "👁️"}
                  </button>
                </div>
              </div>

              {/* Password Rules */}
              <div className="onboarding-password-rules">
                <div className="onboarding-password-rule">
                  <span className="onboarding-rule-icon">✓</span>
                  <span className="onboarding-rule-text">{uiText.passwordRule1}</span>
                </div>
                <div className="onboarding-password-rule">
                  <span className="onboarding-rule-icon">✓</span>
                  <span className="onboarding-rule-text">{uiText.passwordRule2}</span>
                </div>
                <div className="onboarding-password-rule">
                  <span className="onboarding-rule-icon">✓</span>
                  <span className="onboarding-rule-text">{uiText.passwordRule3}</span>
                </div>
              </div>

              {/* Set Password Button */}
              <button
                onClick={handleSetPassword}
                className="submit-btn onboarding-password-submit"
                disabled={isLoading}
              >
                {isLoading ? "Creating Account..." : uiText.setPassword}
              </button>
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

              {/* Continue Button */}
              <button
                onClick={handleCompleteProfile}
                className="submit-btn onboarding-continue-btn"
                disabled={isLoading || !username.trim() || !selectedAvatar}
              >
                {isLoading ? "Saving..." : "CONTINUE"}
              </button>
            </div>
          </div>
        );
      case 3:
        return (
          <div className="onboarding-benefits">
            <h2 className="onboarding-section-title">{uiText.benefitsTitle}</h2>
            <div className="onboarding-benefits-list">
              <div className="onboarding-benefit-item">
                <span className="onboarding-benefit-check">✓</span>
                <span className="onboarding-benefit-text">{uiText.benefit1}</span>
              </div>
              <div className="onboarding-benefit-item">
                <span className="onboarding-benefit-check">✓</span>
                <span className="onboarding-benefit-text">{uiText.benefit2}</span>
              </div>
              <div className="onboarding-benefit-item">
                <span className="onboarding-benefit-check">✓</span>
                <div className="onboarding-benefit-text">
                  <span>{uiText.benefit3}</span>
                  <ul className="onboarding-benefit-sublist">
                    <li>{uiText.resource1}</li>
                    <li>{uiText.resource2}</li>
                    <li>{uiText.resource3}</li>
                    <li>{uiText.resource4}</li>
                    <li>{uiText.resource5}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        );
      case 4:
        return (
          <div className="onboarding-confirmation">
            <h2 className="onboarding-confirmation-title">{uiText.confirmationTitle}</h2>
            <p className="onboarding-confirmation-subtitle">
              {uiText.confirmationSubtitle}
            </p>
            <button
              onClick={() => navigate(withUi("/pathway", uiLang))}
              className="submit-btn onboarding-confirmation-button"
            >
              {uiText.getStarted}
            </button>
          </div>
        );
      default:
        return null;
    }
  };

  const renderProgressDots = () => {
    const dots = [];
    for (let i = 0; i < 4; i++) {
      dots.push(
        <div
          key={i}
          className={`onboarding-dot ${i === step ? 'active' : ''}`}
        />
      );
    }
    return dots;
  };

  return (
    <div className="onboarding-main">
      {/* Logo positioned outside and above the container */}
      <div className="onboarding-top-logo">
        <img
          src="/images/full-logo.webp"
          alt="Pailin Abroad Logo"
          className="onboarding-full-logo"
        />
      </div>

      <div className="onboarding-container">
        {/* Top Navigation - now just language toggle */}
        <nav className="onboarding-nav">
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
              >
                {uiText.next} →
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
