import React from "react";
import "../Styles/ChooseUs.css";

const ChooseUs = () => {
  const reasons = [
    "Natural, everyday English",
    "Content by native English speakers",
    "All content translated to Thai",
    "Listen to real conversations",
    "Learn common mistakes by Thais"
  ];

  return (
    <section className="choose-us">
      <div className="choose-us-card">
        <div className="choose-us-content">
          <h2>Why choose Pailin Abroad?</h2>
          <ul className="reasons-list">
            {reasons.map((reason, index) => (
              <li key={index} className="reason-item">
                <img src="/images/filled-checkmark-lesson-complete.webp" alt="checkmark" className="checkmark-icon" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default ChooseUs;
