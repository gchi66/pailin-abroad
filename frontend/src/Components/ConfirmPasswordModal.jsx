import React, { useEffect, useState } from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/LoginModal.css";

const ConfirmPasswordModal = ({ isOpen, onClose, onConfirm, isLoading, error }) => {
  const [password, setPassword] = useState("");
  const { ui } = useUiLang();

  useEffect(() => {
    if (isOpen) {
      setPassword("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (event) => {
    event.preventDefault();
    onConfirm(password);
  };

  return (
    <div className="login-modal">
      <div className="login-modal-content">
        <button className="login-modal-close" onClick={onClose}>
          &times;
        </button>
        <h2>{t("authModals.confirmPassword.title", ui)}</h2>
        <form onSubmit={handleSubmit}>
          {error && <div className="login-error-message">{error}</div>}
          <div className="login-form-group">
            <label className="login-form-label">{t("authModals.confirmPassword.label", ui)}</label>
            <input
              type="password"
              className="login-form-input"
              placeholder={t("authModals.confirmPassword.placeholder", ui)}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            className={`login-submit-btn ${isLoading ? "loading" : ""}`}
            disabled={isLoading}
          >
            {isLoading
              ? t("authModals.confirmPassword.confirming", ui)
              : t("authModals.confirmPassword.confirm", ui)}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ConfirmPasswordModal;
