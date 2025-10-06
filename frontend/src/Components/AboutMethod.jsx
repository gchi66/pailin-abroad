// AboutMethod.jsx
import React, { useState } from "react";
import "../Styles/AboutMethod.css";

const AboutMethod = () => {
  const [expandedCards, setExpandedCards] = useState({ 0: true });

  const toggleCard = (index) => {
    setExpandedCards(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const cards = [
    {
      header: "So, what's this site about?",
      text: "Pailin is a 21-year-old girl from Thailand. She will be studying abroad for one year at UCLA, while staying with a host family in Los Angeles. Follow her as she navigates friendships, love, family, school, work, and life in a new country.",
      align: "left"
    },
    {
      header: "How does Pailin Abroad work?",
      text: "Pailin is the main character of Pailin Abroad. She is a 21-year-old Thai girl from Bangkok. She will study abroad in Los Angeles for one year, and she will stay with a host family. Through each dialogue, you'll get to know Pailin herself, as well as the friends and family she interacts with while in the USA. Follow Pailin as she navigates a new country, new friends, new love interests, a new school, a new culture, and a new way of life. Pailin will start to feel like someone you know in no time.",
      align: "right"
    },
    {
      header: "Who's Pailin?",
      text: "Pailin is the main character of Pailin Abroad. She is a 21-year-old Thai girl from Bangkok. She will study abroad in Los Angeles for one year, and she will stay with a host family. Through each dialogue, you'll get to know Pailin herself, as well as the friends and family she interacts with while in the USA. Follow Pailin as she navigates a new country, new friends, new love interests, a new school, a new culture, and a new way of life. Pailin will start to feel like someone you know in no time.",
      align: "left",
      hasImage: true
    },
    {
      header: "What are the conversations about?",
      text: "The conversations range from a variety of topics - family, friendship, love, work, school, travel, hobbies, etc. The focus is on everyday, casual language. There already exist many resources for ESL learners to learn business English, or for conversations about specific topics, like 'At the Post Office.' So, our focus is on casual conversation with friends, family, love interests, and co-workers. Our conversations will allow you to get a feel for how you can show your personality through English. Sometimes the characters are excited, sometimes angry, sometimes upset, sometimes stressed, sometimes silly - just like you! Pailin and the other characters will eventually feel like your own friends and family. We hope that by being invested in the characters, you'll be eager to follow along on Pailin's journey in Los Angeles.",
      align: "right"
    }
  ];

  return (
    <div className="about-method-cards-container">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`about-method-card ${expandedCards[index] ? 'expanded' : ''}`}
          onClick={() => toggleCard(index)}
        >
          <div className={`about-method-card-header-container ${expandedCards[index] ? 'expanded' : ''}`}>
            <span className="about-method-card-header">
              {card.header}
            </span>
            <svg
              className={`about-method-card-arrow ${expandedCards[index] ? 'expanded' : ''}`}
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#1E1E1E"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {expandedCards[index] && (
            <>
              <hr className="about-method-card-line" />

              <div className="about-method-card-content">
                {card.hasImage && card.align === 'left' && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}

                <span className="about-method-card-text">
                  {card.text}
                </span>

                {card.hasImage && card.align === 'right' && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
};

// Ensure this is the only default export in the file
export default AboutMethod;
