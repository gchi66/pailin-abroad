import React, { useState } from "react";
import "../Styles/Characters.css";

const charactersData = [
  {
    name: "Pailin",
    description:
      "I’m Pailin! I’m a 21-year-old girl from Bangkok. I’ll be studying abroad in Los Angeles for a year. I’m easy-going and so excited to try new experiences. I think I’ll fit right in in LA!",
    image: "pailin.png",
    color: "#F34254",
  },
  {
    name: "Character 2",
    description:
      "Hi, I'm Character 2! I bring a unique perspective and love exploring new opportunities.",
    image: "character2.png",
    color: "#42B4F3",
  },
  {
    name: "Character 3",
    description:
      "Hello, I'm Character 3! I enjoy meeting new people and sharing my experiences.",
    image: "character3.png",
    color: "#42B4F3",
  },
  {
    name: "Character 4",
    description:
      "Hey, I'm Character 4! I’m always up for a challenge and love learning new things.",
    image: "character4.png",
    color: "#42B4F3",
  },
  {
    name: "Character 5",
    description:
      "Hi there, I'm Character 5! I’m passionate about traveling and making new connections.",
    image: "character5.png",
    color: "#42B4F3",
  },
  {
    name: "Character 6",
    description:
      "Hi, I’m Character 6! I enjoy creative storytelling and making people laugh.",
    image: "character6.png",
    color: "#42B4F3",
  },
];

const Characters = () => {
  const [selectedCharacter, setSelectedCharacter] = useState(charactersData[0]);

  return (
    <section className="characters-section">
      <h2 className="characters-title">MEET THE CHARACTERS</h2>
      <div className="main-character">
        <div className="main-image">
          <img
            src={`images/${selectedCharacter.image}`}
            alt={selectedCharacter.name}
          />
        </div>
        <div className="main-description">
          <p>{selectedCharacter.description}</p>
        </div>
      </div>
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
    </section>
  );
};

export default Characters;
