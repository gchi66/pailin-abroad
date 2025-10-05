import React, { useState } from "react";
import "../Styles/Contact.css";

const Contact = () => {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    message: ""
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prevData) => ({ ...prevData, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:5000/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });
      if (response.ok) {
        alert("Message sent successfully!");
        setFormData({ name: "", email: "", message: "" });
      } else {
        alert("Error sending message.");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Something went wrong.");
    }
  };

  return (
    <div className="contact-page-container">
      {/* page header */}
      <header className="contact-page-header">
        <h1 className="contact-page-header-text">CONTACT US</h1>
      </header>

      <div className="contact-elements-container">

        {/* card */}
        <div className="contact-card">
          We’re here to help. Please check out our FAQ page to see if your question has already been answered. To contact us with further questions or feedback, please message us through any of the following platforms, or fill out the form below.
        </div>

        {/* form */}
        <div className="form-container">
          <form className="contact-form" onSubmit={handleSubmit}>
            <label htmlFor="name">Name</label>
            <input
              type="text"
              id="name"
              name="name"
              placeholder="Name"
              value={formData.name}
              onChange={handleChange}
              required
            />

            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              placeholder="Email"
              value={formData.email}
              onChange={handleChange}
              required
            />

            <label htmlFor="message">
              Type your question, suggestion, or feedback.
              Please provide as much detail as possible.
            </label>
            <textarea
              id="message"
              name="message"
              placeholder="Your message here..."
              rows="5"
              value={formData.message}
              onChange={handleChange}
              required
            ></textarea>

            <button type="submit">Submit</button>
          </form>
        </div>

        {/* pailin image */}
        <img
          src="/images/characters/pailin-blue-right.png"
          alt="Pailin"
          className="contact-pailin-image"
        />
      </div>
    </div>
  );
};

export default Contact;
