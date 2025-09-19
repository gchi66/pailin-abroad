import React, { useState } from "react";
import MembershipFeatures from "../Components/MembershipFeatures";
import "../Styles/Membership.css";

const Membership = () => {
  const [hoveredCard, setHoveredCard] = useState(null);
  const [selectedPlan, setSelectedPlan] = useState(null);

  const plans = [
    {
      id: "6-month",
      duration: "6 MONTHS",
      price: "300฿",
      period: "month",
      savings: "Save 25%",
      bestFor: "Achieving long-term fluency and mastery",
      isRecommended: true,
      totalPrice: 1800,
      originalPrice: 2400,
      monthlyPrice: 300
    },
    {
      id: "3-month",
      duration: "3 MONTHS",
      price: "350฿",
      period: "month",
      savings: "Save 12.5%",
      bestFor: "Committing to consistent progress",
      isRecommended: false,
      totalPrice: 1050,
      originalPrice: 1200,
      monthlyPrice: 350
    },
    {
      id: "1-month",
      duration: "1 MONTH",
      price: "400฿",
      period: "month",
      savings: null,
      bestFor: "Trying out our lessons at your own pace",
      isRecommended: false,
      totalPrice: 400,
      originalPrice: null,
      monthlyPrice: 400
    }
  ];

  const handleCardClick = (plan) => {
    setSelectedPlan(plan);
  };

  // Calculate 6-month cost based on selected plan
  const calculateSixMonthCost = () => {
    if (!selectedPlan) return null;
    return selectedPlan.monthlyPrice * 6;
  };

  return (
    <div className="membership-container">
      {/* Header Section */}
      <div className="membership-header">
        <h1 className="membership-title">Choose the best plan for you</h1>
        <p className="membership-subtitle">
          For the price of one private English lesson, get a whole month of Pailin Abroad!
        </p>
      </div>

      {/* Pricing Cards */}
      <div className="pricing-cards-container">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className={`pricing-card ${selectedPlan?.id === plan.id ? 'selected' : ''} ${hoveredCard === plan.id ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredCard(plan.id)}
            onMouseLeave={() => setHoveredCard(null)}
            onClick={() => handleCardClick(plan)}
          >
            {plan.savings && (
              <div className={`savings-badge ${plan.isRecommended ? 'recommended-badge' : 'regular-badge'}`}>
                {plan.savings}
              </div>
            )}

            <div className="card-content">
              <div className="left-section">
                <div className="plan-duration">{plan.duration}</div>
                <div className="best-for-section">
                  <span className="best-for-label">BEST FOR:</span>
                  <span className="best-for-text">{plan.bestFor}</span>
                </div>
              </div>

              <div className="right-section">
                <div className="price-section">
                  <span className="price">{plan.price}</span>
                  <span className="period">/ {plan.period}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pricing Summary - Only show when a plan is selected */}
      {selectedPlan && (
        <div className="pricing-summary">
          <div className="discounted-price">
            <span className="final-price">{calculateSixMonthCost()}฿</span>
            <span className="for-6-months">(6 months at {selectedPlan.price}/month)</span>
          </div>
        </div>
      )}

      {/* Join Button */}
      <div className="join-section">
        <button className="join-now-btn">
          JOIN NOW!
        </button>
      </div>

      {/* Guarantee */}
      <div className="guarantee-section">
        <p className="guarantee-text">
          <strong>100% money-back guarantee</strong> within 30 days of your purchase if you're not completely satisfied with your membership. But, we're confident you'll love Pailin Abroad!
        </p>
      </div>

      <MembershipFeatures />
    </div>
  );
};

export default Membership;
