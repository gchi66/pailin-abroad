import React, { useState } from "react";
import "../Styles/Contact.css";
import { API_BASE_URL } from "../config/api";

const Contact = () => {
  const [status, setStatus] = useState("idle");
  const [feedback, setFeedback] = useState("");
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
        setFeedback("Message sent successfully! We'll get back to you soon.");
        setFormData({ name: "", email: "", message: "" });
      } else {
        let errorMessage = "Error sending message. Please try again.";
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
      setFeedback("Something went wrong. Please try again.");
    }
  };

  return (
    <div className="contact-page-container">
      {/* page header */}
      <header className="contact-page-header">
        <h1 className="contact-page-header-text">Contact Us</h1>
        <p className="contact-page-header-subtitle">We'd love to hear from you! Reach out with questions or feedback</p>
      </header>

      <div className="contact-elements-container">

        {/* card */}
        <div className="contact-card">
          We’re here to help. Please check out our FAQ page to see if your question has already been answered. To contact us with further questions or feedback, please message us through any of the following platforms, or fill out the form below.
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
                {feedback || (status === "sending" ? "Sending your message..." : "")}
              </div>
            )}
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

            <button type="submit" disabled={status === "sending"}>
              {status === "sending" ? "Sending..." : "Submit"}
            </button>
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
