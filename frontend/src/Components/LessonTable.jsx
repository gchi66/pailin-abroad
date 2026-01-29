import React from "react";
import AudioButton from "./AudioButton";
import "../Styles/LessonTable.css";

export default function LessonTable({
  data,
  snipIdx,
  phrasesSnipIdx,
  phraseId,
  phraseVariant = 0,
  tableVisibility = null,
  enableCellHighlights = false
}) {
  const thaiRegex = /[\u0E00-\u0E7F]/;

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

    const renderTextWithLinks = (text, keyPrefix) => {
      const linkRe = /\[link:([^\]]+)\]([\s\S]*?)\[\/link\]/g;
      const out = [];
      let lastIndex = 0;
      let match;
      let linkIdx = 0;

      while ((match = linkRe.exec(text)) !== null) {
        const [raw, hrefRaw, linkText] = match;
        const start = match.index;
        const end = start + raw.length;
        if (start > lastIndex) {
          out.push(<React.Fragment key={`${keyPrefix}-text-${linkIdx}`}>{text.slice(lastIndex, start)}</React.Fragment>);
        }
        let href = (hrefRaw || "").trim();
        if (href.startsWith("https://pa.invalid/lesson/")) {
          href = href.replace("https://pa.invalid", "");
        }
        if (href.startsWith("https://pa.invalid/topic-library/")) {
          href = href.replace("https://pa.invalid", "");
        }
        out.push(
          <a
            key={`${keyPrefix}-link-${linkIdx}`}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: "underline", color: "#676769" }}
          >
            {linkText || href}
          </a>
        );
        lastIndex = end;
        linkIdx += 1;
      }

      if (lastIndex < text.length) {
        out.push(<React.Fragment key={`${keyPrefix}-tail`}>{text.slice(lastIndex)}</React.Fragment>);
      }

      return out.length ? out : text;
    };

    const lines = cellText.split("\n");

    return lines.map((line, lineIdx) => {
      const { cleanText, audioKeys } = parseAudioInText(line);
      const isThaiLine = thaiRegex.test(cleanText) && !/[A-Za-z]/.test(cleanText);
      const lineSpanClassName = isThaiLine ? "lesson-table-thai" : undefined;
      const content = renderTextWithLinks(cleanText, `cell-${rowIdx}-${colIdx}-${lineIdx}`);

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
            <span className={lineSpanClassName}>{content}</span>
          </div>
        );
      }

      // Regular line without audio
      return (
        <div key={lineIdx} className={lineSpanClassName}>
          {content}
        </div>
      );
    });
  };

  const normalizeCell = (cell) => {
    if (cell && typeof cell === "object") {
      return {
        text: cell.text || "",
        colspan: cell.colspan,
        rowspan: cell.rowspan,
        background: cell.background
      };
    }

    return { text: cell || "" };
  };

  return (
    <div
      className={
        `lesson-table-wrapper${
          tableVisibility ? ` table-visibility-${tableVisibility}` : ""
        }`
      }
    >
      <table>
        <tbody>
          {data.cells.map((row, rIdx) => {
            const rowSpans = [];
            let spanSlots = 0;
            for (let prevRow = 0; prevRow < rIdx; prevRow += 1) {
              const prev = data.cells[prevRow] || [];
              prev.forEach((cell) => {
                if (cell && typeof cell === "object" && cell.rowspan > 1) {
                  const spanEnd = prevRow + cell.rowspan - 1;
                  if (rIdx <= spanEnd) {
                    const spanCols = typeof cell.colspan === "number" && cell.colspan > 1 ? cell.colspan : 1;
                    spanSlots += spanCols;
                  }
                }
              });
            }
            for (let i = 0; i < spanSlots; i += 1) {
              rowSpans.push(1);
            }

            return (
              <tr key={rIdx}>
                {row.map((cell, cIdx) => {
                  if (rowSpans[cIdx] > 0) {
                    return null;
                  }
                  const rowHasColspan = row.some(
                    (rowCell) => rowCell && typeof rowCell === "object" && rowCell.colspan > 1
                  );
                  if (rowHasColspan && (cell == null || (typeof cell === "string" && cell.trim() === ""))) {
                    return null;
                  }
                  if (cell == null) return null;
                  const { text, colspan, rowspan, background } = normalizeCell(cell);
                  const colSpan = typeof colspan === "number" && colspan > 1 ? colspan : undefined;
                  const rowSpan = typeof rowspan === "number" && rowspan > 1 ? rowspan : undefined;
                  const cellStyle = enableCellHighlights && background
                    ? { background }
                    : undefined;

                  return (
                    <td key={cIdx} colSpan={colSpan} rowSpan={rowSpan} style={cellStyle}>
                      {renderCellContent(text, rIdx, cIdx)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
