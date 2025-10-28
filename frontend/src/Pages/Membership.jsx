import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import MembershipFeatures from "../Components/MembershipFeatures";
import QuickSignupModal from "../Components/QuickSignupModal";
import { useAuth } from "../AuthContext";
import "../Styles/Membership.css";

const Membership = () => {
  const [hoveredCard, setHoveredCard] = useState(null);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showPlanWarning, setShowPlanWarning] = useState(false);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const navigate = useNavigate();
  const { user } = useAuth();

  // Always start the membership page at the top when navigated to
  useEffect(() => {
    // Instant jump to top to avoid preserved scroll position from previous page
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    document.body.classList.add("membership-page");
    return () => {
      document.body.classList.remove("membership-page");
    };
  }, []);

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

  // Calculate pricing display based on selected plan
  const calculatePricingDisplay = () => {
    if (!selectedPlan) return null;

    // For 1-month plan, show only final price
    if (selectedPlan.id === "1-month") {
      return {
        showComparison: false,
        finalPrice: selectedPlan.totalPrice,
        description: `(${selectedPlan.duration.toLowerCase()})`
      };
    }

    // For 3 and 6 month plans, show comparison
    return {
      showComparison: true,
      originalPrice: selectedPlan.originalPrice,
      finalPrice: selectedPlan.totalPrice,
      description: `(${selectedPlan.duration.toLowerCase()})`
    };
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
          {(() => {
            const pricing = calculatePricingDisplay();
            return (
              <div className="pricing-comparison">
                {pricing.showComparison && (
                  <span className="original-price">{pricing.originalPrice}฿</span>
                )}
                <span className="final-price">{pricing.finalPrice}฿</span>
                <span className="pricing-description">{pricing.description}</span>
              </div>
            );
          })()}
        </div>
      )}

      {/* Join Button */}
      <div className="join-section">
        <button
          className={`join-now-btn ${!selectedPlan ? 'disabled' : ''}`}
          onClick={() => {
            // If no plan selected, show a transient warning instead of navigating
            if (!selectedPlan) {
              setShowPlanWarning(true);
              // hide after 3 seconds
              setTimeout(() => setShowPlanWarning(false), 3000);
              return;
            }

            // Check if user is authenticated
            if (!user) {
              // Show signup modal if not logged in
              setShowSignupModal(true);
              return;
            }

            // Pass selected plan data to checkout page
            navigate('/checkout', { state: { selectedPlan } });
          }}
          aria-disabled={!selectedPlan}
        >
          JOIN NOW!
        </button>

        {showPlanWarning && (
          <div className="plan-warning" role="status">
            Please select a payment plan
          </div>
        )}
      </div>

      {/* Guarantee */}
      <div className="guarantee-section">
        <p className="guarantee-text">
          <strong>100% money-back guarantee</strong> within 30 days of your purchase if you're not completely satisfied with your membership. But, we're confident you'll love Pailin Abroad!
        </p>
      </div>

      <MembershipFeatures />

      {/* Quick Signup Modal */}
      <QuickSignupModal
        isOpen={showSignupModal}
        onClose={() => setShowSignupModal(false)}
        onSuccess={() => {
          setShowSignupModal(false);
          // User is now logged in, proceed to checkout
          navigate('/checkout', { state: { selectedPlan } });
        }}
      />
    </div>
  );
};

export default Membership;
