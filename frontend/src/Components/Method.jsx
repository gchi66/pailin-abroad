import React from "react";
import "../Styles/Method.css";

const Method = () => {
  return (
    <section className="method-section">
      <div className="method-card">
        <div className="method-box">
          <h2 className="method-title">THE METHOD</h2>
          <p className="method-text">
            Pailin Abroad offers English lessons based on audio conversations
            designed to teach natural, practical, and conversational English.
            Each lesson focuses on a grammar point or key concept, seamlessly
            integrated into real-world dialogue. The dialogues follow Pailin,
            a 21-year-old girl from Thailand, who will be studying abroad at
            UCLA while staying with a host family in Los Angeles. Through her
            journey navigating friendships, love, family, school, work, and
            life in a new country, you’ll gain rich insights into American
            culture, avoid common mistakes Thai learners often face, and most
            importantly, improve your English.
          </p>
        </div>
      </div>
      <div className="graphic-container">
        <img
          src="/images/method-speech-bubbles.webp"
          alt="Speech Bubbles"
          className="dialogue-bubbles"
        />
      </div>
    </section>
  );
};

export default Method;
