import React from "react";
import "../Styles/MembershipFeatures.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const MembershipFeatures = () => {
  const { ui } = useUiLang();
  const featuresCopy = copy.membershipPage?.features ?? {};
  const features = (featuresCopy.items || []).map((item) => pick(item.text, ui));

  return (
    <section className="membership-features-section">
      <div className="membership-features-card">
        <div className="membership-features-box">
          <h2 className="membership-features-title">{pick(featuresCopy.title, ui)}</h2>
          <ul className="membership-features-text">
            {features.map((feature, index) => (
              <li key={`${index}-${feature}`} className="membership-feature-item">
                <img
                  src="/images/blue-checkmark.webp"
                  alt=""
                  aria-hidden="true"
                  className="membership-feature-icon"
                />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default MembershipFeatures;
