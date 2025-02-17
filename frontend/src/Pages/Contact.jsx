import React from "react";
import "../Styles/Contact.css";

const Contact = () => {
  return (
    <div className="contact-page-container">
      {/* page header */}
      <header className="contact-page-header">
        <h1 className="contact-page-header-text">CONTACT US</h1>
        <img src="/images/contact-us-mail-image.webp" alt="Flying Letter" className="contact-header-image" />
      </header>
    </div>
  );
};

export default Contact;
