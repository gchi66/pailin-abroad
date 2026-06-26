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
  const INLINE_MARKER_RE = /(\[X\]|\[✓\]|\[-\]|\[check\])/g;
  const INLINE_MARKER_COLORS = {
    "[X]": "#FD6969",
    "[✓]": "#3CA0FE",
    "[-]": "#28A265",
    "[check]": "#3CA0FE",
  };

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
    const cleanText = text.replace(audioRegex, '');

    return { cleanText, audioKeys };
  };

  const normalizeHref = (hrefRaw) => {
    let href = (hrefRaw || "").trim();
    if (href.startsWith("https://pa.invalid/lesson/")) {
      href = href.replace("https://pa.invalid", "");
    }
    if (href.startsWith("https://pa.invalid/topic-library/")) {
      href = href.replace("https://pa.invalid", "");
    }
    return href;
  };

  const markerLabelFor = (segment) => (
    segment === "[X]" ? "X" :
    segment === "[✓]" ? "✓" :
    segment === "[-]" ? "-" :
    segment === "[check]" ? "✓" :
    segment
  );

  const renderSegmentsWithMarkers = (text, baseStyle, keyPrefix) => {
    const segments = String(text).split(INLINE_MARKER_RE).filter((part) => part !== "");
    return segments.map((segment, segIdx) => {
      const markerColor = INLINE_MARKER_COLORS[segment];
      const style = markerColor
        ? { ...baseStyle, color: markerColor, fontWeight: 600 }
        : baseStyle;
      return (
        <span key={`${keyPrefix}-segment-${segIdx}`} style={style}>
          {markerColor ? markerLabelFor(segment) : segment}
        </span>
      );
    });
  };

  const buildTableLines = (cell) => {
    const sourceInlines = Array.isArray(cell?.inlines) && cell.inlines.length > 0
      ? cell.inlines
      : [{ text: cell?.text || "", bold: false, italic: false, underline: false, link: null }];

    const lines = [];
    let currentLine = { inlines: [], audioKeys: [] };

    const pushCurrentLine = () => {
      lines.push(currentLine);
      currentLine = { inlines: [], audioKeys: [] };
    };

    sourceInlines.forEach((span) => {
      const rawText = typeof span?.text === "string" ? span.text : "";
      const parts = rawText.split("\n");

      parts.forEach((part, idx) => {
        const { cleanText, audioKeys } = parseAudioInText(part);
        if (audioKeys.length > 0) {
          currentLine.audioKeys.push(...audioKeys);
        }
        if (cleanText) {
          currentLine.inlines.push({
            ...span,
            text: cleanText,
          });
        }
        if (idx < parts.length - 1) {
          pushCurrentLine();
        }
      });
    });

    const trimLineInlines = (line) => {
      if (!line.inlines.length) return line;
      const nextInlines = line.inlines.map((span) => ({ ...span }));
      nextInlines[0].text = (nextInlines[0].text || "").replace(/^\s+/, "");
      nextInlines[nextInlines.length - 1].text = (nextInlines[nextInlines.length - 1].text || "").replace(/\s+$/, "");
      return {
        ...line,
        inlines: nextInlines.filter((span) => span.text !== ""),
      };
    };

    if (currentLine.inlines.length > 0 || currentLine.audioKeys.length > 0 || lines.length === 0) {
      lines.push(currentLine);
    }

    return lines.map(trimLineInlines);
  };

  const renderStyledInline = (span, keyPrefix) => {
    const baseStyle = {
      fontWeight: span?.bold ? "bold" : undefined,
      fontStyle: span?.italic ? "italic" : undefined,
      textDecoration: span?.underline ? "underline" : undefined,
      whiteSpace: "pre-wrap",
    };

    if (span?.link) {
      return (
        <a
          key={`${keyPrefix}-link`}
          href={normalizeHref(span.link)}
          target="_blank"
          rel="noopener noreferrer"
          style={{ ...baseStyle, color: "#676769" }}
        >
          {renderSegmentsWithMarkers(span.text || "", { ...baseStyle, color: "#676769" }, keyPrefix)}
        </a>
      );
    }

    return renderSegmentsWithMarkers(span?.text || "", baseStyle, keyPrefix);
  };

  const renderCellContent = (cell, rowIdx, colIdx) => {
    const lines = buildTableLines(cell);

    return lines.map((line, lineIdx) => {
      const joinedText = line.inlines.map((span) => span?.text || "").join("");
      const isThaiLine = thaiRegex.test(joinedText) && !/[A-Za-z]/.test(joinedText);
      const lineSpanClassName = isThaiLine ? "lesson-table-thai" : undefined;
      const content = line.inlines.flatMap((span, spanIdx) =>
        renderStyledInline(span, `cell-${rowIdx}-${colIdx}-${lineIdx}-${spanIdx}`)
      );

      if (line.audioKeys.length > 0) {
        return (
          <div key={lineIdx} className="table-line-with-audio" style={{ display: "flex", alignItems: "center", marginBottom: "4px" }}>
            <AudioButton
              audioKey={line.audioKeys[0]}
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
        inlines: Array.isArray(cell.inlines) ? cell.inlines : null,
        colspan: cell.colspan,
        rowspan: cell.rowspan,
        background: cell.background
      };
    }

    return { text: cell || "", inlines: null };
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
                  const normalizedCell = normalizeCell(cell);
                  const { colspan, rowspan, background } = normalizedCell;
                  const colSpan = typeof colspan === "number" && colspan > 1 ? colspan : undefined;
                  const rowSpan = typeof rowspan === "number" && rowspan > 1 ? rowspan : undefined;
                  const cellStyle = enableCellHighlights && background
                    ? { background }
                    : undefined;

                  return (
                    <td key={cIdx} colSpan={colSpan} rowSpan={rowSpan} style={cellStyle}>
                      {renderCellContent(normalizedCell, rIdx, cIdx)}
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
