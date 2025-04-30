import React, { useState } from "react";

export default function OpenEndedExercise({ exercise }) {
  const { prompt, options = [] } = exercise;

  const [answers, setAnswers]   = useState(Array(options.length).fill(""));
  const [checked, setChecked]   = useState(false);

  const metaOf = (idx) => {
    const m = options[idx].match(/\{(.+)\}$/);
    if (!m) return { keywords: [], min_chars: 20 };
    const parts = m[1].split(";").map(p => p.trim());
    const keywords = (parts.find(p => p.startsWith("keywords")) || "")
                      .split(":")[1]?.split(",").map(w=>w.trim()).filter(Boolean) || [];
    const min = parseInt((parts.find(p => p.startsWith("min_chars")) || "").split(":")[1], 10);
    return { keywords, min_chars: isNaN(min) ? 20 : min };
  };

  const passed = (idx) => {
    if (!checked) return null;
    const { keywords, min_chars } = metaOf(idx);
    const ans = answers[idx].toLowerCase();
    const hasWords = keywords.every(k => ans.includes(k.toLowerCase()));
    return ans.length >= min_chars && hasWords;
  };

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
  };

  return (
    <div className="oe-wrap">
      <p className="oe-prompt">{prompt}</p>

      {options.map((qLine, idx) => {
        const question = qLine.replace(/\{.+\}$/, "").trim();
        return (
          <div key={idx} className="oe-question">
            <p>{question}</p>
            <textarea
              rows={2}
              value={answers[idx]}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={checked}
            />
            {checked && (
              <span className={`oe-mark ${passed(idx) ? "correct" : "wrong"}`}>
                {passed(idx) ? "✓" : "✗"}
              </span>
            )}
          </div>
        );
      })}

      {!checked && (
        <button className="oe-btn" onClick={() => setChecked(true)}>
          Check
        </button>
      )}
    </div>
  );
}
