import React, { useState } from "react";
import "../Styles/FAQPage.css";

const FAQPage = () => {
  const [selectedSection, setSelectedSection] = useState("Account & Membership");

  return (
    <div className="faq-page-container">
      {/* Page header */}
      <header className="faq-page-header">
        <h1 className="faq-page-header-text">Frequently Asked Questions</h1>
        <p className="faq-page-header-subtitle">All your questions, answered here!</p>
      </header>

      {/* Section navigation */}
      <div className="faq-section-btns-container">
        <button
          className={`faq-section-btn ${selectedSection === "Account & Membership" ? "active" : ""}`}
          onClick={() => setSelectedSection("Account & Membership")}
        >
          ACCOUNT & MEMBERSHIP
        </button>
        <button
          className={`faq-section-btn ${selectedSection === "Lessons & Content" ? "active" : ""}`}
          onClick={() => setSelectedSection("Lessons & Content")}
        >
          LESSONS & CONTENT
        </button>
        <button
          className={`faq-section-btn ${selectedSection === "Billing & Payments" ? "active" : ""}`}
          onClick={() => setSelectedSection("Billing & Payments")}
        >
          BILLING & PAYMENTS
        </button>
        <button
          className={`faq-section-btn ${selectedSection === "Technical Support" ? "active" : ""}`}
          onClick={() => setSelectedSection("Technical Support")}
        >
          TECHNICAL SUPPORT
        </button>
      </div>

      {/* Section content */}
      <div className={`faq-section-content ${selectedSection === "Account & Membership" ? "visible" : ""}`}>
        {/* Account & Membership content will go here */}
        <p>Account & Membership FAQs coming soon...</p>
      </div>
      <div className={`faq-section-content ${selectedSection === "Lessons & Content" ? "visible" : ""}`}>
        {/* Lessons & Content content will go here */}
        <p>Lessons & Content FAQs coming soon...</p>
      </div>
      <div className={`faq-section-content ${selectedSection === "Billing & Payments" ? "visible" : ""}`}>
        {/* Billing & Payments content will go here */}
        <p>Billing & Payments FAQs coming soon...</p>
      </div>
      <div className={`faq-section-content ${selectedSection === "Technical Support" ? "visible" : ""}`}>
        {/* Technical Support content will go here */}
        <p>Technical Support FAQs coming soon...</p>
      </div>
    </div>
  );
};

export default FAQPage;
