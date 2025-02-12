import React, { useState }  from "react";
import "../Styles/LessonsIndex.css";


const LessonsIndex = () => {
  const [isLevelOpen, setIsLevelOpen] = useState(true);
  const lessons = [
    { id: 1, title: "Hi, I'm Pailin", subtitle: "Learn how to greet someone" },
    { id: 2, title: "It's nice to meet you", subtitle: "What to say when meeting someone for the first time" },
    { id: 3, title: "How are you?", subtitle: "How to ask how someone is doing" },
    { id: 4, title: "Good morning, Joey!", subtitle: "How to greet someone in the morning" },
    { id: 5, title: "What's your name?", subtitle: "How to ask someone's name politely" },
    { id: 6, title: "I'm excited!", subtitle: "How to express excitement" },
    { id: 7, title: "How old are you?", subtitle: "How to ask someone’s age" },
    { id: 8, title: "Thanks, I made it!", subtitle: "How to respond to compliments" },
    { id: 9, title: "You're a good cook", subtitle: "How to compliment someone's cooking" },
    { id: 10, title: "Chiang Mai is a beautiful city", subtitle: "How to describe a place" },
    { id: 11, title: "Where are you from?", subtitle: "How to ask about someone's hometown" },
    { id: 12, title: "Do you like Thai food?", subtitle: "How to ask about food preferences" },
    { id: 13, title: "This is my family", subtitle: "How to introduce family members" },
    { id: 14, title: "What do you do?", subtitle: "How to ask about someone's job" },
    { id: 15, title: "I love traveling!", subtitle: "How to talk about travel experiences" },
  ];

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-header-text">LESSON LIBRARY</h1>
        <img src="/images/books-lesson-library.webp" alt="Library Books" className="header-image" />
      </header>
      <div className="lesson-library">
        <p className="lesson-subtitle">
          Not sure where to start? Take our <a href="#">Free Placement Test</a>.
        </p>

        <div className="lesson-levels">
          <button className="level-btn">BEGINNER</button>
          <button className="level-btn">LOWER INTERMEDIATE</button>
          <button className="level-btn">UPPER INTERMEDIATE</button>
          <button className="level-btn">ADVANCED</button>
        </div>

        <div className="lesson-btns">
          <button className="tab-btn">LEVEL 1</button>
          <button className="tab-btn">LEVEL 2</button>
          <button className="tab-btn">LEVEL 3</button>
          <button className="tab-btn">LEVEL 4</button>
        </div>

        {/* <div className={`level-container ${isLevelOpen ? "open" : ""}`}>
          <div className="level-header" onClick={() => setIsLevelOpen(!isLevelOpen)}>
            Level 1
            <span>{isLevelOpen ? "▲" : "▼"}</span>
          </div> */}
        <div className="level-wrapper">
          <div className="level-container">
            <div className="level-header">
              <div className="level-text-graphic">
                <span className="level-header-text">LEVEL 1</span>
                <img src="/images/red-level-icon-clipboard.webp" alt="Red Clipboard" className="level-header-image" />
              </div>
              <div className="backstory-arrow-group">
                <span className="backstory-header-text">VIEW BACKSTORY</span>
                <span className="backstory-arrow">▲</span>
              </div>
            </div>
            <div className="level-content">
              <div className="lesson-list">
                {lessons.map((lesson) => (
                  <div key={lesson.id} className="lesson-item">
                    <h2 className="lesson-name">{lesson.title}</h2>
                    <p className="lesson-desc">{lesson.subtitle}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LessonsIndex;
