import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import MembershipFeatures from "../Components/MembershipFeatures";
import QuickSignupModal from "../Components/QuickSignupModal";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";
import "../Styles/Membership.css";

const Membership = () => {
  const [hoveredCard, setHoveredCard] = useState(null);
  const [selectedPlanId, setSelectedPlanId] = useState("6-month");
  const [pricingState, setPricingState] = useState({
    loading: true,
    error: null,
    regionKey: null,
    currency: null,
    plans: []
  });
  const [showPlanWarning, setShowPlanWarning] = useState(false);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const touchStateRef = useRef({ x: 0, y: 0, dragging: false, suppressClick: false, touchStartTime: 0 });
  const scrollStateRef = useRef({ startY: 0, scrolled: false });
  const DRAG_THRESHOLD = 10;
  const navigate = useNavigate();
  const { user } = useAuth();
  const { ui } = useUiLang();
  const membershipCopy = copy.membershipPage;
  const translate = (node) => pick(node, ui);

  // Always start the membership page at the top when navigated to
  useEffect(() => {
    // Instant jump to top to avoid preserved scroll position from previous page
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadPricing = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/pricing`);
        if (!response.ok) {
          throw new Error("Failed to load pricing");
        }
        const data = await response.json();
        if (cancelled) return;
        setPricingState({
          loading: false,
          error: null,
          regionKey: data.region_key,
          currency: data.currency,
          plans: data.plans || []
        });
      } catch (err) {
        if (cancelled) return;
        setPricingState({
          loading: false,
          error: err?.message || "Failed to load pricing",
          regionKey: null,
          currency: null,
          plans: []
        });
      }
    };
    loadPricing();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (pricingState.loading || pricingState.plans.length === 0) return;
    const availableIds = new Set(pricingState.plans.map((plan) => plan.billing_period));
    availableIds.add("lifetime");
    if (!availableIds.has(selectedPlanId)) {
      const preferred = availableIds.has("6-month")
        ? "6-month"
        : pricingState.plans[0].billing_period;
      setSelectedPlanId(preferred);
    }
  }, [pricingState, selectedPlanId]);

  useEffect(() => {
    document.body.classList.add("membership-page");
    return () => {
      document.body.classList.remove("membership-page");
    };
  }, []);

  const currencySymbol = pricingState.currency === "USD" ? "$" : "฿";
  const formatAmount = (value) => {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  };
  const formatWithSymbol = (value) => `${currencySymbol}${formatAmount(value)}`;

  const billingPeriodToCopyKey = {
    "monthly": "oneMonth",
    "3-month": "threeMonth",
    "6-month": "sixMonth"
  };

  const monthsByPeriod = {
    "monthly": 1,
    "3-month": 3,
    "6-month": 6
  };

  const monthlyTier = pricingState.plans.find((plan) => plan.billing_period === "monthly");
  const baseMonthlyPrice = monthlyTier ? Number(monthlyTier.amount_per_month) : null;

  const isUsdPricing = pricingState.currency === "USD";
  const lifetimePrice = isUsdPricing ? 150 : 3500;
  const lifetimeOriginalPrice = lifetimePrice * 2;
  const lifetimePlan = {
    id: "lifetime",
    billingPeriod: "lifetime",
    duration: pick(membershipCopy.lifetime?.title, ui),
    bestFor: pick(membershipCopy.lifetime?.bestFor, ui),
    includesLabel: pick(membershipCopy.lifetime?.includesLabel, ui),
    includes: (membershipCopy.lifetime?.includes || []).map((item) => pick(item, ui)),
    paymentLabel: pick(membershipCopy.lifetime?.paymentLabel, ui),
    bestValue: pick(membershipCopy.lifetime?.bestValue, ui),
    price: formatWithSymbol(lifetimePrice),
    originalPriceDisplay: formatWithSymbol(lifetimeOriginalPrice),
    totalPrice: lifetimePrice,
    originalPrice: lifetimeOriginalPrice,
    currency: pricingState.currency
  };

  if (pricingState.loading) {
    return (
      <main className="page-loading-page">
        <div className="page-loading-inner">
          <img
            src="/images/characters/pailin_blue_circle_right.webp"
            alt={translate(membershipCopy.loadingImageAlt)}
            className="page-loading-image"
          />
        </div>
      </main>
    );
  }

  if (pricingState.error) {
    return (
      <main className="page-loading-page">
        <div className="page-loading-inner is-error">
          <img
            src="/images/characters/pailin_blue_circle_right.webp"
            alt={translate(membershipCopy.loadingImageAlt)}
            className="page-loading-image"
          />
          <div className="page-loading-error-title">
            {translate(membershipCopy.loadingErrorTitle)}
          </div>
          <div className="page-loading-error-body">
            {translate(membershipCopy.loadingErrorBody)}
          </div>
        </div>
      </main>
    );
  }

  const planDefinitions = [...pricingState.plans]
    .sort((a, b) => {
      const aMonths = monthsByPeriod[a.billing_period] || 0;
      const bMonths = monthsByPeriod[b.billing_period] || 0;
      return bMonths - aMonths;
    })
    .map((plan) => {
    const copyKey = billingPeriodToCopyKey[plan.billing_period] || "oneMonth";
    const months = monthsByPeriod[plan.billing_period] || 1;
    const originalPrice = baseMonthlyPrice && months > 1 ? baseMonthlyPrice * months : null;
    const monthlyPrice = Number(plan.amount_per_month);
    const originalMonthlyPrice = Number.isFinite(monthlyPrice) ? monthlyPrice * 2 : null;
    return {
      id: plan.billing_period,
      price: formatWithSymbol(plan.amount_per_month),
      periodKey: "month",
      isRecommended: plan.billing_period === "6-month",
      totalPrice: Number(plan.amount_total),
      originalPrice,
      monthlyPrice,
      originalMonthlyPrice,
      billingPeriod: plan.billing_period,
      currency: pricingState.currency,
      copyKey
    };
    });

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

  const allPlans = [lifetimePlan, ...plans];
  const selectedPlan = allPlans.find((plan) => plan.id === selectedPlanId) || null;

  const handleCardClick = (planId) => {
    setSelectedPlanId(planId);
  };

  const handleTouchStart = (event) => {
    const touch = event.touches[0];
    touchStateRef.current = {
      x: touch.clientX,
      y: touch.clientY,
      dragging: false,
      suppressClick: false,
      touchStartTime: Date.now()
    };
    scrollStateRef.current = {
      startY: window.scrollY,
      scrolled: false
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

  const handleTouchEnd = (planId, event) => {
    const endTouch = event.changedTouches?.[0];
    if (endTouch) {
      const dx = endTouch.clientX - touchStateRef.current.x;
      const dy = endTouch.clientY - touchStateRef.current.y;
      if (Math.hypot(dx, dy) > DRAG_THRESHOLD) {
        touchStateRef.current.suppressClick = true;
        setTimeout(() => {
          touchStateRef.current.suppressClick = false;
        }, 300);
        return;
      }
    }

    if (touchStateRef.current.dragging) {
      touchStateRef.current.suppressClick = true;
      setTimeout(() => {
        touchStateRef.current.suppressClick = false;
      }, 300);
      return;
    }

    const duration = Date.now() - touchStateRef.current.touchStartTime;
    if (duration < 500) {
      handleCardClick(planId);
    }
  };

  const handleTouchCancel = () => {
    touchStateRef.current.dragging = true;
    touchStateRef.current.suppressClick = true;
  };

  const handleClickFallback = (planId, event) => {
    if (!touchStateRef.current.touchStartTime) {
      handleCardClick(planId);
      return;
    }
    const scrollDelta = Math.abs(window.scrollY - scrollStateRef.current.startY);
    if (scrollDelta > 5) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    if (touchStateRef.current.suppressClick) {
      event.preventDefault();
      event.stopPropagation();
      touchStateRef.current.suppressClick = false;
      return;
    }
    handleCardClick(planId);
  };

  // Calculate pricing display based on selected plan
  const calculatePricingDisplay = (plan) => {
    if (!plan) return null;

    if (plan.id === "lifetime") {
      return {
        showComparison: Number.isFinite(plan.originalPrice),
        originalPrice: plan.originalPrice,
        finalPrice: plan.totalPrice
      };
    }

    // For 1-month plan, show only final price
    if (plan.id === "monthly") {
      return {
        showComparison: false,
        finalPrice: plan.totalPrice
      };
    }

    // For 3 and 6 month plans, show comparison
    return {
      showComparison: Boolean(plan.originalPrice),
      originalPrice: plan.originalPrice,
      finalPrice: plan.totalPrice
    };
  };

  return (
    <div className="membership-container">
      {/* Header Section */}
      <div className="membership-header">
        <h1 className="membership-title">
          <span className="membership-title-highlight">
            {pick(membershipCopy.titleHighlight, ui)}
          </span>{" "}
          {pick(membershipCopy.titleRest, ui)}
        </h1>
        <p className="membership-subtitle">
          {pick(membershipCopy.subtitle, ui)}
        </p>
      </div>
      <img
        className="membership-launch-banner"
        src="/images/membership_launch_pricing_banner.webp"
        alt="Membership launch pricing banner"
      />

      {/* Pricing Cards */}
      <div className="pricing-cards-container">
        {!pricingState.loading && !pricingState.error && (
          <div
            className={`pricing-card lifetime-card ${selectedPlanId === lifetimePlan.id ? 'selected' : ''} ${hoveredCard === lifetimePlan.id ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredCard(lifetimePlan.id)}
            onMouseLeave={() => setHoveredCard(null)}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={(event) => handleTouchEnd(lifetimePlan.id, event)}
            onTouchCancel={handleTouchCancel}
            onClick={(event) => handleClickFallback(lifetimePlan.id, event)}
          >
            <div className="lifetime-header">
              <div className="lifetime-title">{lifetimePlan.duration}</div>
              <div className="lifetime-payment desktop-only">{lifetimePlan.paymentLabel}</div>
            </div>

            <div className="lifetime-top-row">
              <div className="lifetime-best-for">
                <span className="best-for-label">{pick(membershipCopy.bestForLabel, ui)}</span>
                <span className="best-for-text">{lifetimePlan.bestFor}</span>
              </div>
              <div className="lifetime-payment mobile-only">{lifetimePlan.paymentLabel}</div>
              <div className="lifetime-price">
                <span className="lifetime-original-price">{lifetimePlan.originalPriceDisplay}</span>
                <span className="price lifetime-final-price">{lifetimePlan.price}</span>
              </div>
            </div>

            <div className="lifetime-divider" />

            <div className="lifetime-body">
              <div className="lifetime-includes">
                <div className="lifetime-includes-label">{lifetimePlan.includesLabel}</div>
                <ul className="lifetime-includes-list">
                  {lifetimePlan.includes.map((item) => (
                    <li key={item} className="lifetime-includes-item">{item}</li>
                  ))}
                </ul>
              </div>
              <div className="lifetime-badge">{lifetimePlan.bestValue}</div>
            </div>
          </div>
        )}
        {!pricingState.loading && !pricingState.error && (
          <div className="lifetime-followup">
            Not ready for lifetime access? Choose a monthly plan below
          </div>
        )}
        {!pricingState.loading && !pricingState.error && plans.map((plan) => (
          <div
            key={plan.id}
            className={`pricing-card ${selectedPlanId === plan.id ? 'selected' : ''} ${hoveredCard === plan.id ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredCard(plan.id)}
            onMouseLeave={() => setHoveredCard(null)}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={(event) => handleTouchEnd(plan.id, event)}
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
                  {Number.isFinite(plan.originalMonthlyPrice) && (
                    <span className="original-monthly-price">
                      {formatWithSymbol(plan.originalMonthlyPrice)}
                    </span>
                  )}
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
                  <span className="original-price">{formatWithSymbol(pricing.originalPrice)}</span>
                )}
                <span className="final-price">{formatWithSymbol(pricing.finalPrice)}</span>
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
        selectedPlan={selectedPlan}
        onSuccess={(email) => {
          setShowSignupModal(false);
          // User is now logged in, proceed to checkout
          const emailParam = email ? `?email=${encodeURIComponent(email)}` : "";
          navigate(`/checkout${emailParam}`, { state: { selectedPlan } });
        }}
      />
    </div>
  );
};

export default Membership;
