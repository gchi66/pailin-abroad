import React from "react";
import "../Styles/About.css";


const About = () => {
  return (
    <section className="about-section">
      <div className="about-card">
        <h2 className="about-title">THE STORY</h2>
        <p>
          Pailin is a 21-year-old girl from Thailand. She will be studying abroad for one year at UCLA, while staying with a host family in Los Angeles. Follow her as she navigates friendships, love, family, school, work, and life in a new country.
        </p>
      </div>

      <div className="about-card">
        <h2 className="about-title">THE METHOD</h2>
        <p>
          Pailin Abroad offers over 200 lessons based on audio conversations, all created by native English speakers from the US. This lets you learn practical, natural, and conversational English.
        </p>
        <p>
          Each lesson covers a grammar point, an important word, or an English concept*. The topic appears throughout the conversation to give you useful, real-world context.
        </p>
        <p>
          Along your learning journey with Pailin, you’ll gain rich insights into American culture, avoid common mistakes that Thai ESL learners make, and most importantly, improve your English.
        </p>
        <p>Take the leap with Pailin and try a free lesson!</p>
        <div className="buttons">
          <button className="free-lessons">FREE LESSONS</button>
          <button className="learn-more">LEARN MORE</button>
        </div>
      </div>
    </section>
  );
};

export default About;
