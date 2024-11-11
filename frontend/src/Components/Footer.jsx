import React from "react";
import "../Styles/Footer.css";

const Footer = () => {
  const handleChatClick = () => {
    alert("Chat feature coming soon!");
  };

  return (
    <footer>
      <button className="chat-button" onClick={handleChatClick}>
        Let's Chat!
      </button>
    </footer>
  );
};

export default Footer;
