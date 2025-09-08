import React from "react";
import "../Styles/FreeLessonCards.css";

const cards = [
  {
    level: "BEGINNER",
    title: "Surfing at Venice Beach",
    focus: "LESSON FOCUS",
    description: "Habits and routines with present simple tense",
  },
  {
    level: "INTERMEDIATE",
    title: "Look, there's a celebrity!",
    focus: "LESSON FOCUS",
    description: "How to use 'There is' and 'There are'",
  },
  {
    level: "ADVANCED",
    title: "At the baseball game",
    focus: "LESSON FOCUS",
    description: "Practice -ing and -ed adjectives",
  },
  {
    level: "EXPERT",
    title: "Spaghetti sauce everywhere!",
    focus: "LESSON FOCUS",
    description: "Discourse markers and filler words",
  },
];

const FreeLessonCards = () => (
  <section className="free-lesson-cards">
    {cards.map((card, idx) => (
      <div className="fl-card" key={idx}>
      <span className="fl-card-level">{card.level}</span>
      <h3 className="fl-card-title">{card.title}</h3>
      <img src="/images/globe.webp" alt="Lesson globe" className="fl-card-img" />
      <span className="fl-card-focus">{card.focus}</span>
      <p className="fl-card-desc">{card.description}</p>
      <button className="fl-card-btn">GO TO LESSON</button>
      </div>
    ))}
  </section>
);

export default FreeLessonCards;
