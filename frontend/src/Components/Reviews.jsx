import React from "react";
import "../Styles/Reviews.css";



const reviews = [
  {
    name: "BEER",
    location: "Bangkok, Thailand",
    image: "1-reviewer-image.webp", // Replace with the actual image path
    text: "I loved using Pailin Abroad – Pailin’s adventures made learning feel fun and engaging. The lessons were easy to follow and helped me improve my listening and comprehension skills in a natural way.",
  },
  {
    name: "SEEN",
    location: "Los Angeles, CA, USA",
    image: "2-reviewer-image.webp", // Replace with the actual image path
    text: "I loved using Pailin Abroad – Pailin’s adventures made learning feel fun and engaging. The lessons were easy to follow and helped me improve my listening and comprehension skills in a natural way.",
  },
  {
    name: "PRAEW",
    location: "Chiang Mai, Thailand",
    image: "3-reviewer-image.webp", // Replace with the actual image path
    text: "Pailin Abroad quickly helped me feel comfortable speaking with restaurant customers here in LA, and helped me improve my English enough that I’ve started making good friends out here.",
  },
];

const Reviews = () => {
  return (
    <section className="reviews-section">
      <div className="reviews-container">
        <h2 className="reviews-title">REVIEWS</h2>
        <div className="review-cards-container">
          {reviews.map((review, index) => (
            <div key={index} className="review-card">
              <p className="review-text">{review.text}</p>
              <div className="photo-name-container">
                <img
                  src={`images/${review.image}`}
                  alt={`${review.name} - ${review.location}`}
                  className="review-image"
                />
                <div className ="name-location-container">
                  <span className="review-name">
                    {review.name}
                  </span>
                  <span className="review-location">
                    {review.location}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Reviews;
