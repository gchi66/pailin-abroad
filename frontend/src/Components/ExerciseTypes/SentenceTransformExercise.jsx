import React, { useState } from "react";

/**
 * Expected exercise structure (example):
 * {
 *   kind: "sentence_transform",
 *   prompt: "Rewrite using 'let's'.",
 *   options: [
 *      "We should go to the store. || Let's go to the store.",
 *      "We should leave soon.      || Let's leave soon."
 *   ]
 * }
 *
 * Everything before "||" is the displayed stem; everything after is a model answer.
 */
export default function SentenceTransformExercise({ exercise }) {
  const { prompt, options = [] } = exercise;
  const [answers, setAnswers]   = useState(Array(options.length).fill(""));
  const [checked, setChecked]   = useState(false);

  const splits = options.map(line => {
    const [stem, expected = ""] = line.split("||").map(s => s.trim());
    return { stem, expected };
  });

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
  };

  const passed = (idx) => {
    if (!checked) return null;
    const want = splits[idx].expected.toLowerCase().replace(/\s+/g, " ").trim();
    const got  = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();
    return got === want;
  };

  return (
    <div className="st-wrap">
      <p className="st-prompt">{prompt}</p>

      {splits.map(({ stem }, idx) => (
        <div key={idx} className="st-row">
          <p className="st-stem">{stem}</p>
          <input
            type="text"
            value={answers[idx]}
            onChange={(e) => handleChange(idx, e.target.value)}
            disabled={checked}
          />
          {checked && (
            <span className={`st-mark ${passed(idx) ? "correct" : "wrong"}`}>
              {passed(idx) ? "✓" : "✗"}
            </span>
          )}
        </div>
      ))}

      {!checked && (
        <button className="st-btn" onClick={() => setChecked(true)}>
          Check
        </button>
      )}
    </div>
  );
}
