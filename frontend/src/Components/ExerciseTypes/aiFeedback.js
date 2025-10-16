import React from "react";

const STATUS_ICONS = {
  correct: "✓",
  partial: "⚠️",
  incorrect: "✗",
};

const DEFAULT_MESSAGES = {
  correct: "Great job!",
  partial: "Almost there—review the suggestion.",
  incorrect: "Keep practicing! Check the feedback below.",
};

export function deriveStatus(correct, score) {
  if (correct === true) return "correct";
  if (correct === false) {
    if (typeof score === "number" && score >= 0.5) {
      return "partial";
    }
    return "incorrect";
  }
  return null;
}

export function InlineStatus({ state }) {
  if (!state) return null;
  if (state.loading) {
    return <span className="ai-inline-status checking">…</span>;
  }

  const status = deriveStatus(state.correct, state.score);
  if (!status) return null;

  return (
    <span className={`ai-inline-status ${status}`}>
      {STATUS_ICONS[status]}
    </span>
  );
}

export function QuestionFeedback({ state, layout = "block" }) {
  if (!state) return null;
  const layoutClass = layout === "inline" ? "inline" : "";

  if (state.loading) {
    return (
      <div className={`ai-feedback-box checking ${layoutClass}`}>
        <span className="ai-feedback-icon">…</span>
        <div className="ai-feedback-text">
          <p className="ai-feedback-en">Checking...</p>
        </div>
      </div>
    );
  }

  const status = deriveStatus(state.correct, state.score);
  if (!status) return null;

  const icon = STATUS_ICONS[status];
  const feedbackEn = state.feedback?.en?.trim()
    ? state.feedback.en
    : DEFAULT_MESSAGES[status];
  const feedbackTh = state.feedback?.th?.trim() || "";

  return (
    <div className={`ai-feedback-box ${status} ${layoutClass}`}>
      <span className="ai-feedback-icon">{icon}</span>
      <div className="ai-feedback-text">
        <p className="ai-feedback-en">{feedbackEn}</p>
        {feedbackTh && <p className="ai-feedback-th">{feedbackTh}</p>}
      </div>
    </div>
  );
}
