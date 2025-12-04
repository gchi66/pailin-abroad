import React from "react";
import { Link } from "react-router-dom";
import "../Styles/Breadcrumbs.css";

const Breadcrumbs = ({ items = [], className = "" }) => {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const combinedClassName = ["breadcrumbs", className].filter(Boolean).join(" ");

  return (
    <nav className={combinedClassName} aria-label="Breadcrumb">
      <ol className="breadcrumbs-list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const key = item?.label || index;

          return (
            <li key={key} className="breadcrumbs-item">
              {item?.to && !isLast ? (
                <Link to={item.to} className="breadcrumbs-link">
                  {item.label}
                </Link>
              ) : (
                <span className="breadcrumbs-current">{item?.label}</span>
              )}
              {!isLast && <span className="breadcrumbs-separator">→</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default Breadcrumbs;
