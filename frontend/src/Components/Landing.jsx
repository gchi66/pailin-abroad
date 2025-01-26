import React from "react";
import "../Styles/Landing.css";


const Landing = () => {
  return (
    <section className="landing">
      <div className="pailin-image">
        <div className="profile-pic"></div>
      </div>
      <div className="landing-content">
        <h2>PAILIN ABROAD!</h2>
        <p>EFFECTIVE ENGLISH LEARNING FOR THAI SPEAKERS</p>
        <ul>
          <li>200+ audio lessons</li>
          <li>Content by native English speakers</li>
          <li>Everyday, useful English</li>
        </ul>
        <div className="landing-buttons">
          <button className="sign-up">JOIN</button>
          <button className="free-lessons">FREE LESSONS</button>
        </div>
      </div>
    </section>
  );
};

export default Landing;
