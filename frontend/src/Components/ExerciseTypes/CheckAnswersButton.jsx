import React, { useEffect, useMemo, useRef, useState } from "react";
import { copy, pick } from "../../ui-lang/i18n";
import "../../Styles/CheckAnswersButton.css";

export default function CheckAnswersButton({
  onClick,
  disabled,
  isChecking = false,
  label,
  checkingLabel,
  hasIncompleteAnswers = false,
  contentLang = "en",
  className = "apply-submit",
  wrapperClassName = "",
  type = "button",
}) {
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const wrapperRef = useRef(null);
  const lastPointerTypeRef = useRef(null);
  const coarsePointerActiveRef = useRef(false);
  const tooltipId = useMemo(
    () => `check-answer-tooltip-${Math.random().toString(36).slice(2)}`,
    []
  );
  const shouldEnableTooltip = Boolean(disabled && hasIncompleteAnswers);
  const supportsPointerEvents = useMemo(() => {
    if (typeof window === "undefined") return false;
    return "PointerEvent" in window;
  }, []);
  const tooltipText = pick(copy.lessonContent.completeBeforeCheck, contentLang);

  const hideTooltip = () => setTooltipVisible(false);
  const showTooltip = () => setTooltipVisible(true);

  useEffect(() => {
    if (!tooltipVisible) return;

    const handlePointerDown = (event) => {
      const wrapper = wrapperRef.current;
      if (!wrapper) return;
      if (wrapper.contains(event.target)) return;
      hideTooltip();
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        hideTooltip();
      }
    };

    const handleScroll = () => hideTooltip();

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, [tooltipVisible]);

  useEffect(() => {
    if (!shouldEnableTooltip && tooltipVisible) {
      hideTooltip();
    }
  }, [shouldEnableTooltip, tooltipVisible]);

  const isCoarsePointer = (pointerType = "") =>
    pointerType === "touch" ||
    pointerType === "pen" ||
    pointerType === "stylus";

  const handlePointerEnter = (event) => {
    if (!supportsPointerEvents) return;
    if (!shouldEnableTooltip) return;
    if (isCoarsePointer(event.pointerType)) return;
    showTooltip();
  };

  const handlePointerLeave = (event) => {
    if (!supportsPointerEvents) return;
    if (isCoarsePointer(event.pointerType)) return;
    hideTooltip();
  };

  const handlePointerDown = (event) => {
    if (!supportsPointerEvents) return;
    lastPointerTypeRef.current = event.pointerType || null;
    if (!shouldEnableTooltip) return;
    if (isCoarsePointer(event.pointerType)) {
      coarsePointerActiveRef.current = true;
      setTooltipVisible((prev) => !prev);
      return;
    }
    coarsePointerActiveRef.current = false;
    hideTooltip();
  };

  const handleMouseEnter = () => {
    if (supportsPointerEvents) return;
    if (!shouldEnableTooltip) return;
    showTooltip();
  };

  const handleMouseLeave = () => {
    if (supportsPointerEvents) return;
    hideTooltip();
  };

  const handleTouchStart = (event) => {
    if (supportsPointerEvents) return;
    if (!shouldEnableTooltip) return;
    coarsePointerActiveRef.current = true;
    setTooltipVisible((prev) => !prev);
    event.preventDefault();
    event.stopPropagation();
  };

  const handleFocus = () => {
    if (!shouldEnableTooltip) return;
    showTooltip();
  };

  const handleBlur = () => {
    hideTooltip();
  };

  const handleClickCapture = (event) => {
    if (!shouldEnableTooltip) {
      hideTooltip();
      return;
    }

    if (coarsePointerActiveRef.current) {
      event.preventDefault();
      event.stopPropagation();
      coarsePointerActiveRef.current = false;
      return;
    }

    const pointerType = lastPointerTypeRef.current;
    if (isCoarsePointer(pointerType)) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    hideTooltip();
  };

  const handleKeyDown = (event) => {
    if (!shouldEnableTooltip) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      showTooltip();
    }
  };

  return (
    <div
      ref={wrapperRef}
      className={`check-answers-button ${wrapperClassName}`}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onPointerDown={handlePointerDown}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onClickCapture={handleClickCapture}
      onKeyDown={handleKeyDown}
      tabIndex={shouldEnableTooltip ? 0 : undefined}
      aria-describedby={tooltipVisible ? tooltipId : undefined}
    >
      <button
        type={type}
        className={className}
        onClick={onClick}
        disabled={disabled}
        style={shouldEnableTooltip ? { pointerEvents: "none" } : undefined}
      >
        {isChecking && checkingLabel ? checkingLabel : label}
      </button>
      {shouldEnableTooltip && tooltipVisible && (
        <div className="check-answers-button__tooltip" id={tooltipId} role="status">
          {tooltipText}
        </div>
      )}
    </div>
  );
}
