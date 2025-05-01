import React, { useState } from "react";

/**
 * Updated SentenceTransformExercise component that works with the new data structure:
 * {
 *   kind: "sentence_transform",
 *   title: "Make the sentences negative",
 *   prompt: "",
 *   items: [
 *     {
 *       number: "1",
 *       stem: "I speak Korean.",
 *       correct: null,
 *       answer: "I don't speak Korean."
 *     },
 *     // ...more items
 *   ]
 * }
 */
export default function SentenceTransformExercise({ exercise = {} }) {
  const { title = "", prompt = "", items = [] } = exercise || {};
  const [answers, setAnswers] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
  };

  const passed = (idx) => {
    if (!checked) return null;

    // For already correct sentences (correct === true), the answer should match the stem
    if (items[idx].correct === true) {
      const stem = items[idx].stem.toLowerCase().replace(/\s+/g, " ").trim();
      const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();
      return got === stem;
    }

    // For sentences that need transformation
    const want = items[idx].answer.toLowerCase().replace(/\s+/g, " ").trim();
    const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();
    return got === want;
  };

  console.log('Rendering SentenceTransformExercise with:', exercise);
  return (
    <div className="bg-gray-50 p-6 rounded-lg">
      <h3 className="text-xl font-bold mb-4">{title}</h3>
      {prompt && <p className="mb-6 text-gray-700">{prompt}</p>}

      {items.map((item, idx) => (
        <div key={idx} className="mb-6 border-b pb-4">
          <p className="mb-2 font-medium">{item.number}. {item.stem}</p>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={answers[idx]}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={checked}
              placeholder="Transform the sentence"
              className="border rounded py-2 px-3 w-full"
            />

            {checked && (
              <span className={`flex-shrink-0 font-bold ${passed(idx) ? "text-green-600" : "text-red-600"}`}>
                {passed(idx) ? "✓" : "✗"}
              </span>
            )}
          </div>

          {checked && !passed(idx) && (
            <p className="mt-2 text-sm text-gray-600">
              <span className="font-semibold">Correct answer:</span>{" "}
              {items[idx].correct === true ? items[idx].stem : items[idx].answer}
            </p>
          )}
        </div>
      ))}

      {!checked && (
        <button
          onClick={() => setChecked(true)}
          className="bg-blue-600 text-white py-2 px-6 rounded hover:bg-blue-700"
        >
          Check
        </button>
      )}
    </div>
  );
}
