import React from "react";
import { Link } from "react-router-dom";
import "../Styles/PlanNotice.css";

const PlanNotice = ({ heading, subtext, cta, secondaryCta, footerNote }) => {
  const renderCTA = (buttonProps, isSecondary = false) => {
    if (!buttonProps) return null;

    const className = isSecondary
      ? `plan-notice-cta plan-notice-cta-secondary`
      : "plan-notice-cta";

    if (buttonProps.to) {
      return (
        <Link to={buttonProps.to} className={className}>
          {buttonProps.label}
        </Link>
      );
    }

    if (buttonProps.href) {
      return (
        <a
          href={buttonProps.href}
          className={className}
          target={buttonProps.target || "_self"}
          rel={buttonProps.target === "_blank" ? "noopener noreferrer" : undefined}
        >
          {buttonProps.label}
        </a>
      );
    }

    return (
      <button
        type="button"
        className={className}
        onClick={buttonProps.onClick}
        disabled={buttonProps.disabled}
      >
        {buttonProps.label}
      </button>
    );
  };

  const renderSubtext = () => {
    if (!subtext) return null;

    if (Array.isArray(subtext)) {
      return (
        <div className="plan-notice-subtext">
          {subtext.map((line, index) => (
            <p className="plan-notice-subtext-line" key={index}>
              {line}
            </p>
          ))}
        </div>
      );
    }

    return <p className="plan-notice-subtext plan-notice-subtext-line">{subtext}</p>;
  };

  const primaryCTA = renderCTA(cta);
  const secondaryCTA = renderCTA(secondaryCta, true);

  return (
    <section className="plan-notice">
      {heading && <h2 className="plan-notice-heading">{heading}</h2>}
      {renderSubtext()}
      {(primaryCTA || secondaryCTA) && (
        <div className="plan-notice-cta-group">
          {primaryCTA}
          {secondaryCTA}
        </div>
      )}
      {footerNote && <p className="plan-notice-footer-note">{footerNote}</p>}
    </section>
  );
};

export default PlanNotice;
