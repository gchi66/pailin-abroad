import React, { useState } from "react";
import "../Styles/Characters.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const characterConfig = [
  { slug: "pailin" },
  { slug: "luke" },
  { slug: "chloe" },
  { slug: "mark" },
  { slug: "emily" },
  { slug: "tyler" },
  { slug: "sylvie" },
];

const Characters = () => {
  const { ui } = useUiLang();
  const charactersCopy = copy.home.characters;
  const entries = charactersCopy.entries || [];

  const characters = characterConfig.map(({ slug }, index) => {
    const entry = entries[index] || {};
    return {
      name: pick(entry.name, ui),
      description: pick(entry.description, ui),
      image: `/images/characters/${slug}_meet_the_characters.webp`,
      thumbnail: {
        default: `/images/characters/${slug}_white_circle.webp`,
        active: `/images/characters/${slug}_blue_circle.webp`,
      },
    };
  });

  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedCharacter = characters[selectedIndex] || {};

  return (
    <section className="characters-section">
      <div className="character-card">
        <div className="character-image">
          {selectedCharacter.image && (
            <img src={selectedCharacter.image} alt={selectedCharacter.name} />
          )}
        </div>
        <div className="character-content">
          <h2 className="characters-title">{pick(charactersCopy.title, ui)}</h2>
          <p className="character-description">{selectedCharacter.description}</p>
          <div className="character-thumbnails">
            {characters.map((character, index) => {
              const isSelected = index === selectedIndex;
              const thumbnailSrc = isSelected
                ? character.thumbnail?.active
                : character.thumbnail?.default;

              return (
                <div
                  key={index}
                  className={`thumbnail ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedIndex(index)}
                >
                  {thumbnailSrc && (
                    <img src={thumbnailSrc} alt={`${character.name} thumbnail`} />
                  )}
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
