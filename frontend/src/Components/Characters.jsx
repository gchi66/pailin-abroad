import React, { useState } from "react";
import "../Styles/Characters.css";

const charactersData = [
  {
    name: "Pailin",
    description:
      "I’m Pailin! I’m a 21-year-old girl from Bangkok. I’ll be studying abroad in Los Angeles for a year. I’m easy-going and so excited to try new experiences. I think I’ll fit right in in LA!",
    image: "Pailin-blue.png",
    color: "#F34254",
  },
  {
    name: "Chloe",
    description:
      "I'm Chloe, Pailin's new friend in LA. My dad is Thai, and my mom is French, but I grew up in Thailand. I'm outgoing and lots of fun. I can be a bit clumsy and a bit sassy.",
    image: "Chloe-blue.png",
    color: "#42B4F3",
  },
  {
    name: "Tyler",
    description:
      "I'm Tyler, Pailin's host brother. I'm also a student at UCLA. I can't make up my mind what I want to study - I keep switching my major! I'm a loyal friend who's always up for an adventure.",
    image: "Tyler-blue.png",
    color: "#42B4F3",
  },
  {
    name: "Emily",
    description:
      "I'm Emily, Pailin's host sister. I'm a curious 13-year-old, and I'm super chatty. Sometimes I get myself into trouble, but for the most part, I'm very lovable (I think).",
    image: "Emily-blue.png",
    color: "#42B4F3",
  },
  {
    name: "Sylvie",
    description:
      "I'm Sylvie, Pailin's host mom. I'm from France, and I'm a wine importer. I enjoy trying new foods, warm days at the beach, and spending time with my family.",
    image: "Sylvie-blue.png",
    color: "#42B4F3",
  },
  {
    name: "Mark",
    description:
      "I'm Mark, Pailin's host dad. I'm a busy lawyer, but when I'm not working, I like training for marathons and reading science-fiction novels.",
    image: "Mark-blue.png",
    color: "#42B4F3",
  },
];

const Characters = () => {
  const [selectedCharacter, setSelectedCharacter] = useState(charactersData[0]);

  return (
    <section className="characters-section">
      <div className="character-container">
        <div className="character-image">
          <img
            src={`images/${selectedCharacter.image}`}
            alt={selectedCharacter.name}
          />
        </div>
        <div className="character-card">
          <h2 className="characters-title">MEET THE CHARACTERS</h2>
          <p className="character-description">{selectedCharacter.description}</p>
          <div className="character-thumbnails">
            {charactersData.map((character, index) => (
              <div
                key={index}
                className={`thumbnail ${
                  character.name === selectedCharacter.name ? "selected" : ""
                }`}
                onClick={() => setSelectedCharacter(character)}
              >
                <img src={`images/${character.image}`} alt={character.name} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default Characters;
