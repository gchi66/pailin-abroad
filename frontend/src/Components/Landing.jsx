import React from "react";
import "../Styles/Landing.css";


const Landing = () => {
  return (
    <section className="landing">
      <div className="pailin-image">
        <div className="profile-pic"></div>
      </div>
      <div className="landing-content">
        <h2>I'M PAILIN!</h2>
        <p>PRACTICE YOUR ENGLISH LISTENING SKILLS WITH ME</p>
        <ul>
          <li>200+ audio lessons</li>
          <li>Content by native English speakers</li>
          <li>Everyday, useful English</li>
        </ul>
        <div className="landing-buttons">
          <button className="sign-up">Sign Up</button>
          <button className="free-lessons">Free Lessons</button>
        </div>
      </div>
    </section>
  );
};

export default Landing;
