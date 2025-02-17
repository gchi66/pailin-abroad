import React from "react";
import "../Styles/MembershipFeatures.css";

const MembershipFeatures = () => {
  return (
    <section className="membership-features-section">
      <div className="membership-features-card">
        <div className="membership-features-box">
          <h2 className="membership-features-title">MEMBERSHIP INCLUDES ACCESS TO:</h2>
          <ul className="membership-features-text">
            <li>All 200+ lessons and audio dialogues</li>
            <li>Content written by and spoken by native English speakers</li>
            <li>Real, useful, everyday English - not outdated, formal, and stiff language</li>
            <li>Content translated to Thai by our bilingual team of translators</li>
            <li>Common mistakes Thai ESL learners make and how to correct them</li>
            <li>Writing practice with feedback and corrections from our English team</li>
            <li>Unique insight into American culture</li>
          </ul>
        </div>
      </div>
      <div className="graphic-container">
        <img
          src="/images/stars-membership-features.webp"
          alt="Stars Graphic"
          className="stars-graphic"
        />
      </div>
    </section>
  );
};

export default MembershipFeatures;
