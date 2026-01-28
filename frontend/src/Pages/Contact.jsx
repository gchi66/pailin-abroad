import React, { useState } from "react";
import "../Styles/Contact.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";

const Contact = () => {
  const [status, setStatus] = useState("idle");
  const [feedback, setFeedback] = useState("");
  const { ui } = useUiLang();
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    message: ""
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (status !== "idle") {
      setStatus("idle");
      setFeedback("");
    }
    setFormData((prevData) => ({ ...prevData, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("sending");
    setFeedback("");
    try {
      const response = await fetch(`${API_BASE_URL}/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });
      if (response.ok) {
        setStatus("success");
        setFeedback(t("contactPage.statusSuccess", ui));
        setFormData({ name: "", email: "", message: "" });
      } else {
        let errorMessage = t("contactPage.statusError", ui);
        try {
          const data = await response.json();
          if (data?.message) {
            errorMessage = data.message;
          }
        } catch (error) {
          console.error("Error parsing response:", error);
        }
        setStatus("error");
        setFeedback(errorMessage);
      }
    } catch (error) {
      console.error("Error:", error);
      setStatus("error");
      setFeedback(t("contactPage.statusUnexpected", ui));
    }
  };

  return (
    <div className="contact-page-container">
      {/* page header */}
      <header className="contact-page-header">
        <h1 className="contact-page-header-text">{t("contactPage.title", ui)}</h1>
        <p className="contact-page-header-subtitle">{t("contactPage.subtitle", ui)}</p>
      </header>

      <div className="contact-elements-container">

        {/* card */}
        <div className="contact-card">
          {t("contactPage.cardBody", ui)}
        </div>
        <div className="contact-social-links">
          <a
            href="#"
            className="contact-social-link"
            aria-label="Facebook"
          >
            <img src="/images/facebook_icon.png" alt="Facebook" />
          </a>
          <a
            href="#"
            className="contact-social-link"
            aria-label="Instagram"
          >
            <img src="/images/instagram_icon.png" alt="Instagram" />
          </a>
          <a
            href="#"
            className="contact-social-link"
            aria-label="Line"
          >
            <img src="/images/line_icon.png" alt="Line" />
          </a>
        </div>

        {/* form */}
        <div className="form-container">
          <form className="contact-form" onSubmit={handleSubmit}>
            {status !== "idle" && (
              <div
                className={`contact-form-status ${status === "success" ? "is-success" : ""} ${status === "error" ? "is-error" : ""}`}
                role="status"
                aria-live="polite"
              >
                {feedback || (status === "sending" ? t("contactPage.statusSendingMessage", ui) : "")}
              </div>
            )}
            <label htmlFor="name">{t("contactPage.nameLabel", ui)}</label>
            <input
              type="text"
              id="name"
              name="name"
              placeholder={t("contactPage.namePlaceholder", ui)}
              value={formData.name}
              onChange={handleChange}
              required
            />

            <label htmlFor="email">{t("contactPage.emailLabel", ui)}</label>
            <input
              type="email"
              id="email"
              name="email"
              placeholder={t("contactPage.emailPlaceholder", ui)}
              value={formData.email}
              onChange={handleChange}
              required
            />

            <label htmlFor="message">
              {t("contactPage.messageLabel", ui)}
            </label>
            <textarea
              id="message"
              name="message"
              placeholder={t("contactPage.messagePlaceholder", ui)}
              rows="5"
              value={formData.message}
              onChange={handleChange}
              required
            ></textarea>

            <button type="submit" disabled={status === "sending"}>
              {status === "sending" ? t("contactPage.sending", ui) : t("contactPage.submit", ui)}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
};

export default Contact;
