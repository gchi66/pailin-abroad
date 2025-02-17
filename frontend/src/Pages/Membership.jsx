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
      <section className="subheader-container">
        <span className="subheader-text">
          For the price of one private English lesson, get a whole month of Pailin Abroad!
        </span>
      </section>

      <MembershipFeatures />

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

      <section className="guarantee-container">
        <div className="guarantee-subcontainer">
          <span className="guarantee-header">
            JOIN RISK FREE!
            <svg className="guarantee-underline" viewBox="0 0 150 30" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 20 Q75 12, 145 20" stroke="#FF4545" stroke-width="3" fill="none" stroke-linecap="round"/>
            </svg>
          </span>
          <span className="guarantee-text">
            We’re confident you’ll love Pailin Abroad. However, if for any reason you’re not completely satisfied with your membership, we offer a 100% money-back guarantee within 60 days of your purchase.
          </span>
        </div>
      </section>

    </div>
  );
};


export default Membership;
