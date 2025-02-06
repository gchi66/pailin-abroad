import React, { useState } from "react";
import "../Styles/Characters.css";

const charactersData = [
  {
    name: "Pailin",
    description:
      "I’m Pailin! I’m a 21-year-old girl from Bangkok. I’ll be studying abroad in Los Angeles for a year. I’m easy-going and so excited to try new experiences. I think I’ll fit right in in LA!",
    image: "images/characters/pailin-blue-left.png",
    thumbnail: "images/characters/pailin-white-left.png",
  },
  {
    name: "Chloe",
    description:
      "I'm Chloe, Pailin's new friend in LA. My dad is Thai, and my mom is French, but I grew up in Thailand. I'm outgoing and lots of fun. I can be a bit clumsy and a bit sassy.",
    image: "images/characters/chloe-friend-blue-left.png",
    thumbnail: "images/characters/chloe-friend-white-left.png",
  },
  {
    name: "Tyler",
    description:
      "I'm Tyler, Pailin's host brother. I'm also a student at UCLA. I can't make up my mind what I want to study - I keep switching my major! I'm a loyal friend who's always up for an adventure.",
    image: "images/characters/tyler-brother-blue-left.png",
    thumbnail: "images/characters/tyler-brother-white-left.png",
  },
  {
    name: "Emily",
    description:
      "I'm Emily, Pailin's host sister. I'm a curious 13-year-old, and I'm super chatty. Sometimes I get myself into trouble, but for the most part, I'm very lovable (I think).",
    image: "images/characters/emily-sister-blue-left.png",
    thumbnail: "images/characters/emily-sister-white-left.png",
  },
  {
    name: "Sylvie",
    description:
      "I'm Sylvie, Pailin's host mom. I'm from France, and I'm a wine importer. I enjoy trying new foods, warm days at the beach, and spending time with my family.",
    image: "images/characters/sylvie-mom-blue-left.png",
    thumbnail: "images/characters/sylvie-mom-white-left.png",
  },
  {
    name: "Mark",
    description:
      "I'm Mark, Pailin's host dad. I'm a busy lawyer, but when I'm not working, I like training for marathons and reading science-fiction novels.",
    image: "images/characters/mark-dad-blue-left.png",
    thumbnail: "images/characters/mark-dad-white-left.png",
  },
];

const Characters = () => {
  const [selectedCharacter, setSelectedCharacter] = useState(charactersData[0]);

  return (
    <section className="characters-section">
      <div className="character-container">
        <div className="character-image">
          <img src={selectedCharacter.image} alt={selectedCharacter.name} />
        </div>
        <div className="character-card">
          <h2 className="characters-title">MEET THE CHARACTERS</h2>
          <p className="character-description">{selectedCharacter.description}</p>
          <div className="character-thumbnails">
            {charactersData.map((character, index) => {
              const isSelected = character.name === selectedCharacter.name;
              const thumbnailSrc = isSelected
                ? character.thumbnail.replace("white", "blue")
                : character.thumbnail;

              return (
                <div
                  key={index}
                  className={`thumbnail ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedCharacter(character)}
                >
                  <img src={thumbnailSrc} alt={`${character.name} thumbnail`} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};

export default Characters;
