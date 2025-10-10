import React from "react";
import "../Styles/SignUpCTA.css";

const SignUpCTA = ({ onSignupClick }) => {
  return (
    <section className="signup-cta">
      <h2 className="signup-cta-title">
        Ready to access <em>all</em> our free lessons?
      </h2>
      <button className="signup-cta-button" onClick={onSignupClick}>
        SIGN UP FOR FREE
      </button>
    </section>
  );
};

export default SignUpCTA;
