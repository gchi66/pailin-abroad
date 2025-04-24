import React from "react";
import "../Styles/Footer.css";

const Footer = () => {
  return (
    <footer className="footer">
      {/* Top section in black (#1e1e1e) */}
      <div className="footer-top">
        <div className="footer-container">
          <div className="footer-column">
            <h3 className="footer-title">RESOURCES</h3>
            <ul>
              <li>Lesson Library</li>
              <li>Free Lessons</li>
              <li>Phrases &amp; Phrasal Verbs</li>
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
              <li>Work With Us</li>
            </ul>
          </div>
          <div className="footer-column">
            <h3 className="footer-title">HELP CENTER</h3>
            <ul>
              <li>Contact Us</li>
              <li>FAQ</li>
            </ul>
          </div>
          <div className="footer-column follow-us">
            <h3 className="footer-title">FOLLOW US</h3>
            <div className="social-icons">
              <button className="social-icon-link">
                <img
                  src="images/instagram-icon-black.png"
                  alt="Instagram"
                />
              </button>
              <button className="social-icon-link">
                <img
                  src="images/youtube-icon-black.png"
                  alt="YouTube"
                />
              </button>
              <button className="social-icon-link">
                <img
                  src="images/tiktok-icon-black.png"
                  alt="TikTok"
                />
              </button>
              <button className="social-icon-link">
                <img
                  src="images/facebook-icon-black.png"
                  alt="Facebook"
                />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar in #91CAFF */}
      <div className="footer-bottom">
        <span>Copyright © {new Date().getFullYear()}, Pailin Abroad</span>
      </div>
    </footer>
  );
};

export default Footer;
