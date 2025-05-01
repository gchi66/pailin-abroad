import React, { useState } from "react";

/**
 * Expected shape
 * {
 *   kind:  "open",
 *   title: "Open‑Ended Practice",
 *   prompt: "Answer the questions …",
 *   items: [
 *     {
 *       text: "You accidentally spill water … What do you say?",
 *       keywords: "sorry, water",
 *       min_chars: 20
 *     },
 *     …
 *   ]
 * }
 */
export default function OpenEndedExercise({ exercise }) {
  const { title, prompt, items = [] } = exercise;

  const [answers, setAnswers] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
  };

  const passed = (idx) => {
    if (!checked) return null;

    const kv = (key) => (items[idx][key] || "").toString().trim();
    const keywords = kv("keywords").split(",").map((w) => w.trim()).filter(Boolean);
    const minChars = parseInt(kv("min_chars"), 10) || 20;

    const ans = answers[idx].toLowerCase();
    const hasWords = keywords.every((k) => ans.includes(k.toLowerCase()));
    return ans.length >= minChars && hasWords;
  };

  const handleCheck = () => setChecked(true);
  const handleReset = () => {
    setAnswers(Array(items.length).fill(""));
    setChecked(false);
  };

  return (
    <div className="oe-wrap">
      {title && <h3 className="oe-title">{title}</h3>}
      {prompt && <p className="oe-prompt">{prompt}</p>}

      {items.map((item, idx) => (
        <div key={idx} className="oe-question">
          <p>{item.text}</p>
          <textarea
            rows={3}
            value={answers[idx]}
            onChange={(e) => handleChange(idx, e.target.value)}
            disabled={checked}
            className="oe-textarea"
          />
          {checked && (
            <span className={`oe-mark ${passed(idx) ? "correct" : "wrong"}`}>
              {passed(idx) ? "✓" : "✗"}
            </span>
          )}
        </div>
      ))}

      {!checked ? (
        <button className="oe-btn" onClick={handleCheck}>
          Check
        </button>
      ) : (
        <button className="oe-btn" onClick={handleReset}>
          Reset
        </button>
      )}
    </div>
  );
}
