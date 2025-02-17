import React from "react";
import "../Styles/Membership.css"
import MembershipFeatures from "../Components/MembershipFeatures";

const Membership = () => {
  return (
    <div className="page-container">
      {/* page header */}
      <header className="page-header">
        <h1 className="page-header-text">MEMBERSHIP OPTIONS</h1>
        <img src="/images/membership-card.webp" alt="Membership Card" className="header-image" />
      </header>

      {/* join cards header */}
      <section className="join-cards-header">
        <span className="join-cards-header-text">
          For the price of one private English lesson, get a whole month of Pailin Abroad!
        </span>
      </section>

      {/* cards */}
      <section className="join-cards-container">
        <div className="join-card">
          <span className="join-card-header">MONTHLY PLAN</span>
          <span className="join-card-price">450฿</span>
          <span className="join-card-per-month">450฿ per month</span>
          <button className="select-btn">SELECT</button>
        </div>
        <div className="join-card">
          <span className="join-card-header">6-MONTH PLAN</span>
          <span className="join-card-price">2400฿</span>
          <span className="join-card-per-month">400฿ per month</span>
          <button className="select-btn">SELECT</button>
        </div>
        <div className="join-card">
          <span className="join-card-header">12-MONTH PLAN</span>
          <span className="join-card-price">4200฿</span>
          <span className="join-card-per-month">350฿ per month</span>
          <button className="select-btn">SELECT</button>
        </div>
      </section>

      <MembershipFeatures />
    </div>
  );
};


export default Membership;
