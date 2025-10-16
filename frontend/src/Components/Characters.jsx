import React, { useState } from "react";
import "../Styles/Characters.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const characterAssets = [
  {
    image: "images/characters/pailin-blue-left.png",
    thumbnail: "images/characters/pailin-white-left.png",
  },
  {
    image: "images/characters/chloe-friend-blue-left.png",
    thumbnail: "images/characters/chloe-friend-white-left.png",
  },
  {
    image: "images/characters/tyler-brother-blue-left.png",
    thumbnail: "images/characters/tyler-brother-white-left.png",
  },
  {
    image: "images/characters/emily-sister-blue-left.png",
    thumbnail: "images/characters/emily-sister-white-left.png",
  },
  {
    image: "images/characters/sylvie-mom-blue-left.png",
    thumbnail: "images/characters/sylvie-mom-white-left.png",
  },
  {
    image: "images/characters/mark-dad-blue-left.png",
    thumbnail: "images/characters/mark-dad-white-left.png",
  },
];

const Characters = () => {
  const { ui } = useUiLang();
  const charactersCopy = copy.home.characters;
  const entries = charactersCopy.entries || [];

  const characters = entries.map((entry, index) => ({
    image: characterAssets[index]?.image,
    thumbnail: characterAssets[index]?.thumbnail,
    name: pick(entry.name, ui),
    description: pick(entry.description, ui),
  }));

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
                ? character.thumbnail?.replace("white", "blue")
                : character.thumbnail;

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
