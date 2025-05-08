import React, { useState } from "react";

export default function OpenEndedExercise({ exercise }) {
  const { title, prompt, items = [] } = exercise;

  // Initialize state for each input for each question
  // Structure: [question1: [input1], question2: [input1, input2], etc]
  const [responses, setResponses] = useState(
    items.map(item => Array((item.inputs || 1)).fill(""))
  );
  const [checked, setChecked] = useState(false);

  const handleChange = (qIdx, inputIdx, val) => {
    const nextResponses = [...responses];
    nextResponses[qIdx][inputIdx] = val;
    setResponses(nextResponses);
  };

  const passed = (qIdx) => {
    if (!checked) return null;

    const item = items[qIdx];
    const keywords = (item.keywords || "").split(",").map(k => k.trim().toLowerCase()).filter(Boolean);

    // Check if all inputs for this question contain at least one of the keywords
    return responses[qIdx].every(response => {
      const responseLower = response.toLowerCase();
      return keywords.some(keyword => responseLower.includes(keyword));
    });
  };

  const handleCheck = () => setChecked(true);
  const handleReset = () => {
    setResponses(items.map(item => Array((item.inputs || 1)).fill("")));
    setChecked(false);
  };

  // Determine if all questions have valid responses
  const allAnswered = responses.every((questionInputs, qIdx) => {
    const numInputs = items[qIdx].inputs || 1;
    return questionInputs.filter(Boolean).length === numInputs;
  });

  return (
    <div className="oe-wrap">
      {prompt && <p className="oe-prompt">{prompt}</p>}

      {items.map((item, qIdx) => {
        // Extract keywords for this specific item
        const itemKeywords = (item.keywords || "").split(",").map(k => k.trim()).filter(Boolean);

        return (
          <div key={`question-${qIdx}`} className="oe-question">
            <p className="oe-question-text">{item.number}. {item.question || item.text}</p>

            {/* Render the appropriate number of input fields */}
            {Array.from({ length: item.inputs || 1 }).map((_, inputIdx) => (
              <div key={`input-${qIdx}-${inputIdx}`} className="oe-input-container">
                <textarea
                  rows={3}
                  value={responses[qIdx][inputIdx] || ""}
                  onChange={(e) => handleChange(qIdx, inputIdx, e.target.value)}
                  disabled={checked}
                  className="oe-textarea"
                  placeholder="Type your answer here"
                />
              </div>
            ))}

            {checked && (
              <div className="oe-feedback">
                <span className={`oe-mark ${passed(qIdx) ? "correct" : "wrong"}`}>
                  {passed(qIdx) ? "✓" : "✗"}
                </span>
                {!passed(qIdx) && itemKeywords.length > 0 && (
                  <p className="oe-hint">
                    Remember to use these keywords: {itemKeywords.join(", ")}
                  </p>
                )}
                {item.sample_answer && (
                  <div className="oe-sample-answer">
                    <p><strong>Sample answer:</strong> {item.sample_answer}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="oe-buttons">
        {!checked ? (
          <button
            className="oe-btn check"
            onClick={handleCheck}
            disabled={!allAnswered}
          >
            Check
          </button>
        ) : (
          <button className="oe-btn reset" onClick={handleReset}>
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
