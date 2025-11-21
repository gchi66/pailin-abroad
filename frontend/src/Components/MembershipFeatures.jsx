import React from "react";
import "../Styles/MembershipFeatures.css";

const MembershipFeatures = () => {
  const features = [
    "Our whole lesson library - that’s over 150 lessons!",
    "Our extensive Exercise bank",
    "Common mistakes made by Thai speakers",
    "Often-used phrases and phrasal verbs",
    "Our ESL Topic Library",
    "Cultural notes to help you understand English in context",
    "Comment on any lesson and get feedback from us!",
  ];

  return (
    <section className="membership-features-section">
      <div className="membership-features-card">
        <div className="membership-features-box">
          <h2 className="membership-features-title">Membership includes access to:</h2>
          <ul className="membership-features-text">
            {features.map((feature) => (
              <li key={feature} className="membership-feature-item">
                <img
                  src="/images/blue-checkmark.webp"
                  alt=""
                  aria-hidden="true"
                  className="membership-feature-icon"
                />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default MembershipFeatures;
