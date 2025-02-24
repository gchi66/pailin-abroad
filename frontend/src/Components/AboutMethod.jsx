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


      <div className="method-card-left">
        <div className="pailin-and-header-container">
          <span className="method-card-header">
            Who's Pailin
          </span>
          <img src="/images/characters/im-pailin.png" alt="I'm Pailin" className="im-pailin-pic" />
        </div>
        <hr className="method-card-line" />
        <span className="method-card-text">
          Pailin is the main character of Pailin Abroad. She is a 21-year-old Thai girl from Bangkok. She will study abroad in Los Angeles for one year, and she will stay with a host family.
          Through each dialogue, you'll get to know Pailin herself, as well as the friends and family she interacts with while in the USA. 
          Follow Pailin as she navigates a new country, new friends, new love interests, a new school, a new culture, and a new way of life. Pailin will start to feel like someone you know in no time.
        </span>
      </div>


      <div className="method-card-right">
        <span className="method-card-header">
          What are the conversations about?
        </span>
        <hr className="method-card-line" />
        <span className= "method-card-text">
          The conversations range from a variety of topics - family, friendship, love, work, school, travel, hobbies, etc. The focus is on everyday, casual language.  There already exist many resources for ESL learners to learn business English, or for conversations about specific topics, like 'At the Post Office.' So, our focus is on casual conversation with friends, family, love interests, and co-workers. Our conversations will allow you to get a feel for how you can show your personality through English. Sometimes the characters are excited, sometimes angry, sometimes upset, sometimes stressed, sometimes silly - just like you!  Pailin and the other characters will eventually feel like your own friends and family. We hope that by being invested in the characters, you'll be eager to follow along on Pailin's journey in Los Angeles.        </span>
      </div>
    </div>
  );
};

export default AboutMethod;
