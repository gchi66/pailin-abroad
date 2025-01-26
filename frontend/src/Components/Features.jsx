import React from "react";
import "../Styles/Features.css";

const features = [
  {
    icon: <img src="/images/Globe.png" alt="Globe" />,
    title: "200+ audio lessons",
  },
  {
    icon: <img src="/images/Globe.png" alt="Globe" />,
    title: "Content made by native English speakers",
  },
  {
    icon: <img src="/images/Globe.png" alt="Globe" />,
    title: "Useful, everyday English",
  },
];

const Features = () => {
  return (
    <div className="features-container">
      {features.map((feature, index) => (
        <div key={index} className="feature-item">
          <div className="feature-icon">{feature.icon}</div>
          <p className="feature-text">{feature.title}</p>
        </div>
      ))}
    </div>
  );
};

export default Features;
