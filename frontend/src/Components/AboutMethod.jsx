import React from "react";
import "../Styles/AboutMethod.css"

const AboutMethod = () => {
  return (
    <div className="method-cards-container">
      <div className="method-card-left">
        <span className="method-card-header">
          So, what's this site about?
        </span>
        <hr className="method-card-line" />
        <span className="method-card-text">
          Pailin is a 21-year-old girl from Thailand. She will be studying abroad for one year at UCLA, while staying with a host family in Los Angeles. Follow her as she navigates friendships, love, family, school, work, and life in a new country.
        </span>
      </div>
      <div className="method-card-right">
        <span className="method-card-header">
          How does Pailin Abroad work?
        </span>
        <hr className="method-card-line" />
        <span className= "method-card-text">
          Pailin is the main character of Pailin Abroad. She is a 21-year-old Thai girl from Bangkok. She will study abroad in Los Angeles for one year, and she will stay with a host family. Through each dialogue, you'll get to know Pailin herself, as well as the friends and family she interacts with while in the USA. Follow Pailin as she navigates a new country, new friends, new love interests, a new school, a new culture, and a new way of life. Pailin will start to feel like someone you know in no time.
        </span>
      </div>
      {/* <div className="method-card-left"></div>
      <div className="method-card-right"></div> */}
    </div>
  );
};

export default AboutMethod;
