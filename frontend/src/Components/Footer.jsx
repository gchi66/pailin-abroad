import React from "react";
import "../Styles/Footer.css";

const Footer = () => {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-column">
          <h3 className="footer-title">RESOURCES</h3>
          <ul>
            <li>Lesson Library</li>
            <li>Free Lessons</li>
            <li>Phrases & Phrasal Verbs</li>
            <li>Culture Notes</li>
            <li>Common Mistakes</li>
          </ul>
        </div>
        <div className="footer-column">
          <h3 className="footer-title">ABOUT US</h3>
          <ul>
            <li>Why Choose Us?</li>
            <li>About Pailin Abroad</li>
            <li>Our Team</li>
            <li>Membership Options</li>
          </ul>
        </div>
        <div className="footer-column">
          <h3 className="footer-title">HELP CENTER</h3>
          <ul>
            <li>Contact Us</li>
            <li>FAQ</li>
          </ul>
        </div>
        <div className="footer-column">
          <h3 className="footer-title">PAILIN ABROAD</h3>
          <img
            src="images/Pailin-blue.png"
            alt="Pailin Abroad logo"
            className="footer-logo"
          />
          <div className="social-icons">
            <i className="fab fa-instagram"></i>
            <i className="fab fa-youtube"></i>
            <i className="fab fa-tiktok"></i>
            <i className="fab fa-facebook"></i>
          </div>
        </div>
      </div>
      <div className="footer-bottom">
        <p>Copyright © 2024, Pailin Abroad</p>
      </div>
    </footer>
  );
};

export default Footer;



  // const handleChatClick = () => {
  //   alert("Chat feature coming soon!");
  // };

  // return (
  //   <footer>
  //     <button className="chat-button" onClick={handleChatClick}>
  //       Let's Chat!
  //     </button>
  //   </footer>
  // );
