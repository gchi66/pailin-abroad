import React from "react";
import AudioButton from "./AudioButton";
import "../Styles/LessonTable.css";

export default function LessonTable({
  data,
  snipIdx,
  phrasesSnipIdx,
  phraseId,
  phraseVariant = 0
}) {
  // Helper function to extract audio tags and return cleaned text + audio keys
  const parseAudioInText = (text) => {
    if (!text || typeof text !== 'string') return { cleanText: text, audioKeys: [] };

    const audioRegex = /\[audio:([^\]]+)\]/g;
    const audioKeys = [];
    let match;

    // Extract all audio keys
    while ((match = audioRegex.exec(text)) !== null) {
      audioKeys.push(match[1]);
    }

    // Remove audio tags from display text
    const cleanText = text.replace(audioRegex, '').trim();

    return { cleanText, audioKeys };
  };

  const renderCellContent = (cellText, rowIdx, colIdx) => {
    if (!cellText) return null;

    const lines = cellText.split("\n");

    return lines.map((line, lineIdx) => {
      const { cleanText, audioKeys } = parseAudioInText(line);

      // If line has audio, render with audio button
      if (audioKeys.length > 0) {
        return (
          <div key={lineIdx} className="table-line-with-audio" style={{ display: "flex", alignItems: "center", marginBottom: "4px" }}>
            <AudioButton
              audioKey={audioKeys[0]} // Use first audio key found
              audioIndex={snipIdx}
              phrasesSnipIdx={phrasesSnipIdx}
              phraseId={phraseId}
              phraseVariant={phraseVariant}
              className="mr-2 h-4 w-4 select-none flex-shrink-0"
            />
            <span>{cleanText}</span>
          </div>
        );
      }

      // Regular line without audio
      return <div key={lineIdx}>{cleanText}</div>;
    });
  };

  return (
    <div className="lesson-table-wrapper">
      <table>
        <tbody>
          {data.cells.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => (
                <td key={cIdx}>
                  {renderCellContent(cell, rIdx, cIdx)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
