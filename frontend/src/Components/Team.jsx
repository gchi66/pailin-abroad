import React from "react";
import "../Styles/Team.css";

const teamMembers = [
  {
    name: "CARISSA",
    location: "Co-Founder & Head of Content",
    image: "/images/carissa.webp",
    description:
      "I'm passionate about teaching English to non-native speakers and creating engaging, accessible resources on my ESL education website. I focus on quality, clarity, and inclusivity, offering free lessons and placement tests to guide learners on their journey. With thoughtful design and messaging."
  },
  {
    name: "GRANT",
    location: "Co-Founder & Lead Developer",
    image: "/images/grant.webp",
    description:
      "I'm passionate about teaching English to non-native speakers and creating engaging, accessible resources on my ESL education website. I focus on quality, clarity, and inclusivity, offering free lessons and placement tests to guide learners on their journey. With thoughtful design and messaging."
  },
  {
    name: "LEEH",
    location: "Head Translator",
    image: "/images/rose.webp",
    description:
      "I'm passionate about teaching English to non-native speakers and creating engaging, accessible resources on my ESL education website. I focus on quality, clarity, and inclusivity, offering free lessons and placement tests to guide learners on their journey. With thoughtful design and messaging."
  }
];

const Team = () => {
  return (
    <div className="team-container">
      {teamMembers.map((member, index) => (
        <div className="team-member-card" key={index}>
          <img src={member.image} alt={member.name} className="team-member-image" />
          <div className="team-member-info">
            <span className="member-name">{member.name}</span>
            <span className="member-title">{member.location}</span>
            <hr className="team-underline" />
            <span className="description">{member.description}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Team;
