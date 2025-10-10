import React from "react";
import "../Styles/TakeTheLeapCTA.css";

const TakeTheLeapCTA = ({ onSignupClick }) => {
  return (
    <section className="take-the-leap-cta">
      <h2 className="take-the-leap-cta-title">
        Take the leap with Pailin and sign up today!
      </h2>
      <button className="take-the-leap-cta-button" onClick={onSignupClick}>
        SIGN UP FOR FREE
      </button>
    </section>
  );
};

export default TakeTheLeapCTA;
