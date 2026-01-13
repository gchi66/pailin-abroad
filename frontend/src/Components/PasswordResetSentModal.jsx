import React from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/LoginModal.css";

const PasswordResetSentModal = ({ isOpen, onClose, message }) => {
  const { ui } = useUiLang();
  if (!isOpen) return null;

  const displayMessage = message || t("authModals.resetSent.defaultMessage", ui);

  return (
    <div className="login-modal">
      <div className="login-modal-content">
        <button className="login-modal-close" onClick={onClose}>
          &times;
        </button>
        <h2>{t("authModals.resetSent.title", ui)}</h2>
        <p style={{ textAlign: "center", marginBottom: "1.5rem", color: "#333" }}>
          {displayMessage}
        </p>
        <button className="login-submit-btn" onClick={onClose}>
          {t("authModals.resetSent.ok", ui)}
        </button>
      </div>
    </div>
  );
};

export default PasswordResetSentModal;
