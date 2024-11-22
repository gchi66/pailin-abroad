import React from "react";
import "../Styles/Reviews.css";



const reviews = [
  {
    name: "CARISSA",
    location: "CHIANG MAI",
    image: "Pailin-blue.png", // Replace with the actual image path
    text: "I loved using Pailin Abroad – Pailin’s adventures made learning feel fun and engaging. The lessons were easy to follow and helped me improve my listening and comprehension skills in a natural way.",
  },
  {
    name: "GRANT",
    location: "BANGKOK",
    image: "Pailin-blue.png", // Replace with the actual image path
    text: "I loved using Pailin Abroad – Pailin’s adventures made learning feel fun and engaging. The lessons were easy to follow and helped me improve my listening and comprehension skills in a natural way.",
  },
  {
    name: "SEEN",
    location: "LOS ANGELES",
    image: "Pailin-blue.png", // Replace with the actual image path
    text: "Pailin Abroad quickly helped me feel comfortable speaking with restaurant customers here in LA, and helped me improve my English enough that I’ve started making good friends out here.",
  },
];

const Reviews = () => {
  return (
    <section className="reviews">
      <h2 className="reviews-title">REVIEWS</h2>
      <div className="reviews-container">
        {reviews.map((review, index) => (
          <div key={index} className="review-card">
            <img
              src={`images/${review.image}`}
              alt={`${review.name} - ${review.location}`}
              className="review-image"
            />
            <h3 className="review-name">
              {review.name} · {review.location}
            </h3>
            <p className="review-text">{review.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Reviews;
