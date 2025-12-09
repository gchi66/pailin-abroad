import React from "react";
import "../Styles/Reviews.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const reviewerImages = [
  "1-reviewer-image.webp",
  "2-reviewer-image.webp",
  "3-reviewer-image.webp",
];

const Reviews = () => {
  const { ui } = useUiLang();
  const reviewsCopy = copy.home.reviews;
  const items = reviewsCopy.items || [];

  return (
    <section className="reviews-section">
      <div className="reviews-container">
        <h2 className="reviews-title">{pick(reviewsCopy.title, ui)}</h2>
        <div className="review-cards-container">
          {items.map((review, index) => (
            <div key={index} className="review-item">
              <div className="review-card">
                <p className="review-text">{pick(review.text, ui)}</p>
              </div>
              <div className="photo-name-container">
                <img
                  src={`images/${reviewerImages[index]}`}
                  alt={`${pick(review.name, ui)} - ${pick(review.location, ui)}`}
                  className="review-image"
                />
                <div className="name-location-container">
                  <span className="review-name">
                    {pick(review.name, ui)}
                  </span>
                  <span className="review-location">
                    {pick(review.location, ui)}
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
