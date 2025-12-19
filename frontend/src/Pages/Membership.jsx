import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import MembershipFeatures from "../Components/MembershipFeatures";
import QuickSignupModal from "../Components/QuickSignupModal";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";
import "../Styles/Membership.css";

const Membership = () => {
  const [hoveredCard, setHoveredCard] = useState(null);
  const [selectedPlanId, setSelectedPlanId] = useState("6-month");
  const [showPlanWarning, setShowPlanWarning] = useState(false);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const touchStateRef = useRef({ x: 0, y: 0, dragging: false, suppressClick: false });
  const DRAG_THRESHOLD = 10;
  const navigate = useNavigate();
  const { user } = useAuth();
  const { ui } = useUiLang();
  const membershipCopy = copy.membershipPage;

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

  const planDefinitions = [
    {
      id: "6-month",
      price: "300฿",
      periodKey: "month",
      isRecommended: true,
      totalPrice: 1800,
      originalPrice: 2400,
      monthlyPrice: 300,
      copyKey: "sixMonth"
    },
    {
      id: "3-month",
      price: "350฿",
      periodKey: "month",
      isRecommended: false,
      totalPrice: 1050,
      originalPrice: 1200,
      monthlyPrice: 350,
      copyKey: "threeMonth"
    },
    {
      id: "1-month",
      price: "400฿",
      periodKey: "month",
      isRecommended: false,
      totalPrice: 400,
      originalPrice: null,
      monthlyPrice: 400,
      copyKey: "oneMonth"
    }
  ];

  const plans = planDefinitions.map((plan) => {
    const planCopy = membershipCopy.plans?.[plan.copyKey] ?? {};
    return {
      ...plan,
      duration: pick(planCopy.duration, ui),
      bestFor: pick(planCopy.bestFor, ui),
      savings: planCopy.savings ? pick(planCopy.savings, ui) : null,
      period: pick(membershipCopy.periods?.[plan.periodKey], ui)
    };
  });

  const selectedPlan = plans.find((plan) => plan.id === selectedPlanId) || null;

  const handleCardClick = (planId) => {
    setSelectedPlanId(planId);
  };

  const handleTouchStart = (event) => {
    const touch = event.touches[0];
    touchStateRef.current = {
      x: touch.clientX,
      y: touch.clientY,
      dragging: false,
      suppressClick: false
    };
  };

  const handleTouchMove = (event) => {
    const touch = event.touches[0];
    const dx = touch.clientX - touchStateRef.current.x;
    const dy = touch.clientY - touchStateRef.current.y;
    if (Math.hypot(dx, dy) > DRAG_THRESHOLD) {
      touchStateRef.current.dragging = true;
    }
  };

  const handleTouchEnd = (planId) => {
    if (touchStateRef.current.dragging) {
      touchStateRef.current.suppressClick = true;
      setTimeout(() => {
        touchStateRef.current.suppressClick = false;
      }, 100);
      return;
    }
    handleCardClick(planId);
  };

  const handleTouchCancel = () => {
    touchStateRef.current.dragging = true;
    touchStateRef.current.suppressClick = true;
  };

  const handleClickFallback = (planId, event) => {
    if (touchStateRef.current.suppressClick) {
      event.preventDefault();
      touchStateRef.current.suppressClick = false;
      return;
    }
    handleCardClick(planId);
  };

  // Calculate pricing display based on selected plan
  const calculatePricingDisplay = (plan) => {
    if (!plan) return null;

    // For 1-month plan, show only final price
    if (plan.id === "1-month") {
      return {
        showComparison: false,
        finalPrice: plan.totalPrice
      };
    }

    // For 3 and 6 month plans, show comparison
    return {
      showComparison: true,
      originalPrice: plan.originalPrice,
      finalPrice: plan.totalPrice
    };
  };

  return (
    <div className="membership-container">
      {/* Header Section */}
      <div className="membership-header">
        <h1 className="membership-title">{pick(membershipCopy.title, ui)}</h1>
        <p className="membership-subtitle">
          {pick(membershipCopy.subtitle, ui)}
        </p>
      </div>

      {/* Pricing Cards */}
      <div className="pricing-cards-container">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className={`pricing-card ${selectedPlanId === plan.id ? 'selected' : ''} ${hoveredCard === plan.id ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredCard(plan.id)}
            onMouseLeave={() => setHoveredCard(null)}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={() => handleTouchEnd(plan.id)}
            onTouchCancel={handleTouchCancel}
            onClick={(event) => handleClickFallback(plan.id, event)}
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
                  <span className="best-for-label">{pick(membershipCopy.bestForLabel, ui)}</span>
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
            const pricing = calculatePricingDisplay(selectedPlan);
            return (
              <div className="pricing-comparison">
                {pricing.showComparison && (
                  <span className="original-price">{pricing.originalPrice}฿</span>
                )}
                <span className="final-price">{pricing.finalPrice}฿</span>
              </div>
            );
          })()}
        </div>
      )}

      {/* Join Button */}
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
        {pick(membershipCopy.joinCta, ui)}
      </button>

      {showPlanWarning && (
        <div className="plan-warning" role="status">
          {pick(membershipCopy.planWarning, ui)}
        </div>
      )}

      {/* Guarantee */}
      <div className="guarantee-section">
        <p className="guarantee-text">
          <strong>{pick(membershipCopy.guarantee?.strong, ui)}</strong>{" "}
          {pick(membershipCopy.guarantee?.body, ui)}
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
