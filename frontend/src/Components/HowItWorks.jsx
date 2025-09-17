import React from "react";
import "../Styles/HowItWorks.css";

const HowItWorks = () => {
  const steps = [
    {
      number: "1",
      header: "Listen to the conversation.",
      text: "Move from Beginner to Expert level conversations that follow Pailin as she navigates life in a new country."
    },
    {
      number: "2",
      header: "Dive into the lesson focus",
      text: "Learn the lesson's grammar topic or important word in the context of a real conversation, not just by memorizing rules."
    },
    {
      number: "3",
      header: "Build your fluency",
      text: "Solidify your learning with exercises, common mistakes, useful phrases, and American culture insights."
    }
  ];

  return (
    <section className="how-it-works">
      <h2 className="how-it-works-title">How it works</h2>
      <div className="how-it-works-cards">
        {steps.map((step, index) => (
          <div key={index} className="hiw-card">
            <img src={`/images/number-${step.number}.png`} alt={`Step ${step.number}`} className="hiw-number" />
            <h3 className="hiw-header">{step.header}</h3>
            <p className="hiw-text">{step.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default HowItWorks;
