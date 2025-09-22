import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../Styles/Onboarding.css";

const Onboarding = () => {
  const [step, setStep] = useState(0);
  const [language, setLanguage] = useState("EN");
  const [passwords, setPasswords] = useState({
    newPassword: "",
    confirmPassword: ""
  });
  const [showPasswords, setShowPasswords] = useState({
    newPassword: false,
    confirmPassword: false
  });
  const navigate = useNavigate();

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

  const toggleLanguage = () => {
    setLanguage(language === "EN" ? "TH" : "EN");
    console.log(`Language toggled to: ${language === "EN" ? "TH" : "EN"}`);
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

  const handleSetPassword = () => {
    console.log("Password values:", passwords);
    // TODO: Add password validation and backend call
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
                  Welcome to Pailin Abroad!
                </h1>
                <p className="onboarding-welcome-subtitle">
                  Hi, I'm Pailin! I'm so excited to be your guide on this English journey.
                </p>
                <p className="onboarding-welcome-description">
                  In a few quick steps, we'll get you ready to explore my world and the language I use every day.
                </p>
              </div>
            </div>
          </div>
        );
      case 1:
        return (
          <div className="onboarding-password-setup">
            <h2 className="onboarding-password-title">Let's set up your password</h2>

            <div className="onboarding-password-form">
              {/* New Password Field */}
              <div className="onboarding-input-group">
                <label className="onboarding-input-label">New password</label>
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
                <label className="onboarding-input-label">Confirm password</label>
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
                  <span className="onboarding-rule-text">At least 8 characters</span>
                </div>
                <div className="onboarding-password-rule">
                  <span className="onboarding-rule-icon">✓</span>
                  <span className="onboarding-rule-text">At least 1 number or special character</span>
                </div>
                <div className="onboarding-password-rule">
                  <span className="onboarding-rule-icon">✓</span>
                  <span className="onboarding-rule-text">At least 1 uppercase letter</span>
                </div>
              </div>

              {/* Set Password Button */}
              <button
                onClick={handleSetPassword}
                className="submit-btn onboarding-password-submit"
              >
                SET PASSWORD
              </button>
            </div>
          </div>
        );
      case 2:
        return (
          <div className="onboarding-placeholder">
            <h2>Step 2 content will go here</h2>
          </div>
        );
      case 3:
        return (
          <div className="onboarding-placeholder">
            <h2>Step 3 content will go here</h2>
          </div>
        );
      case 4:
        return (
          <div className="onboarding-placeholder">
            <h2>Step 4 content will go here</h2>
          </div>
        );
      default:
        return null;
    }
  };

  const renderProgressDots = () => {
    const dots = [];
    for (let i = 0; i < 5; i++) {
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
              className={`onboarding-lang-btn ${language === 'EN' ? 'active' : ''}`}
              onClick={() => setLanguage('EN')}
            >
              EN
            </button>
            <span className="onboarding-lang-separator">|</span>
            <button
              className={`onboarding-lang-btn ${language === 'TH' ? 'active' : ''}`}
              onClick={() => setLanguage('TH')}
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
          <div className="onboarding-progress">
            {renderProgressDots()}
          </div>
          <div className="onboarding-navigation">
            {step > 0 && (
              <button
                className="onboarding-back-btn"
                onClick={prevStep}
              >
                ← BACK
              </button>
            )}
            <button
              className="onboarding-next-btn"
              onClick={nextStep}
            >
              {step < 4 ? 'NEXT →' : 'COMPLETE'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
