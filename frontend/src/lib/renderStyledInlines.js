import React from "react";

const TH_RE = /[\u0E00-\u0E7F]/;
const HEX_COLOR_RE = /^#[0-9a-f]{6}$/;
const TH_PUNCT_ONLY_RE = /^[.,!?;:'"(){}[\]<>\/\\\-–—…]+$/;
const INLINE_MARKER_RE = /(\[X\]|\[✓\]|\[-\]|\[check\])/g;
const INLINE_MARKER_COLORS = {
  "[X]": "#FD6969",
  "[✓]": "#3CA0FE",
  "[-]": "#28A265",
  "[check]": "#3CA0FE",
};

function cleanAudioTags(text) {
  if (!text || typeof text !== "string") return text;
  return text
    .replace(/\[audio:[^\]]+\]/g, " ")
    .replace(/[^\S\r\n]+/g, " ")
    .replace(/\s*\n\s*/g, "\n");
}

function normalizeHref(hrefRaw) {
  let href = (hrefRaw || "").trim();
  if (href.startsWith("https://pa.invalid/lesson/")) {
    href = href.replace("https://pa.invalid", "");
  }
  if (href.startsWith("https://pa.invalid/topic-library/")) {
    href = href.replace("https://pa.invalid", "");
  }
  return href;
}

function markerLabelFor(segment) {
  if (segment === "[X]") return "X";
  if (segment === "[✓]") return "✓";
  if (segment === "[-]") return "-";
  if (segment === "[check]") return "✓";
  return segment;
}

export default function renderStyledInlines(inlines, opts = {}) {
  let thaiColor = opts.thaiColor || null;
  const englishColor = opts.englishColor || null;
  const strictThaiSplit = opts.strictThaiSplit === true;
  const keyPrefix = opts.keyPrefix || "inline";
  const lineIsThaiOverride = opts.lineIsThaiOverride === true;

  const normalizedInlines = [];
  (inlines || []).forEach((span) => {
    const text = span?.text || "";
    if (text.includes("\n")) {
      const parts = text.split("\n");
      parts.forEach((part, idx) => {
        if (idx > 0) {
          normalizedInlines.push({ ...span, text: "\n" });
        }
        if (part) {
          normalizedInlines.push({ ...span, text: part });
        }
      });
    } else {
      normalizedInlines.push(span);
    }
  });

  let thaiZoneStartIndex = -1;
  const hasLineBreak = normalizedInlines.some((span) => span?.text === "\n");

  if (hasLineBreak) {
    for (let i = 0; i < normalizedInlines.length; i += 1) {
      const text = cleanAudioTags(normalizedInlines[i]?.text || "");
      if (TH_RE.test(text)) {
        thaiZoneStartIndex = i;
        break;
      }
    }
  } else {
    for (let i = 1; i < normalizedInlines.length; i += 1) {
      const text = cleanAudioTags(normalizedInlines[i]?.text || "");
      if (!TH_RE.test(text)) continue;
      const prevText = cleanAudioTags(normalizedInlines[i - 1]?.text || "");
      if (prevText.includes("(") || TH_PUNCT_ONLY_RE.test(prevText)) {
        thaiZoneStartIndex = i - 1;
        break;
      }
    }
  }

  const hasAnyThai = normalizedInlines.some((span) => TH_RE.test(cleanAudioTags(span?.text || "")));

  if (!hasLineBreak && thaiZoneStartIndex === -1 && !hasAnyThai) {
    thaiColor = null;
  }

  const processedInlines = normalizedInlines.map((span, idx) => {
    const cleanText = cleanAudioTags(span?.text || "");
    const nextSpan = normalizedInlines[idx + 1];
    const originalHadTrailingSpace =
      typeof span?.text === "string" && /[ \t]+$/.test(span.text);
    const styleChangesNext =
      nextSpan &&
      (nextSpan?.underline !== span?.underline ||
        nextSpan?.bold !== span?.bold ||
        nextSpan?.italic !== span?.italic);

    return {
      span,
      cleanText,
      suppressSpaceBefore: styleChangesNext && !originalHadTrailingSpace,
    };
  });

  const collapseInlineMarkers = (entries) => {
    const out = [];
    for (let i = 0; i < entries.length; i += 1) {
      const current = entries[i];
      const next = entries[i + 1];
      const next2 = entries[i + 2];
      const currentText = typeof current?.cleanText === "string" ? current.cleanText : "";
      const nextText = typeof next?.cleanText === "string" ? next.cleanText : "";
      const next2Text = typeof next2?.cleanText === "string" ? next2.cleanText : "";

      const isMarkerMiddle = ["X", "✓", "-", "check"].includes(nextText);
      if (currentText === "[" && isMarkerMiddle && next2Text.startsWith("]")) {
        const rest = next2Text.slice(1);
        out.push({
          ...current,
          cleanText: `[${nextText}]${rest}`,
        });
        i += 2;
        continue;
      }

      out.push(current);
    }
    return out;
  };

  const collapsedInlines = collapseInlineMarkers(processedInlines);

  return collapsedInlines.map((entry, m) => {
    const { span, cleanText } = entry;
    const currentText = typeof cleanText === "string" ? cleanText : "";

    let needsSpaceBefore = false;
    if (m > 0) {
      const prevEntry = collapsedInlines[m - 1];
      if (!prevEntry.suppressSpaceBefore) {
        const prevText = typeof prevEntry.cleanText === "string" ? prevEntry.cleanText : "";
        const prevEndsWithSpaceOrPunct = /[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]$/.test(prevText);
        const currentStartsWithSpaceOrPunct = /^[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]/.test(currentText);
        const prevEndsWithWordChar = /[A-Za-z0-9]$/.test(prevText);
        const currentStartsWithWordChar = /^[A-Za-z0-9]/.test(currentText);
        const hasThaiBoundary = TH_RE.test(prevText) || TH_RE.test(currentText);
        const looksLikeSplitWord = prevEndsWithWordChar && currentStartsWithWordChar;
        needsSpaceBefore =
          !hasThaiBoundary &&
          !looksLikeSplitWord &&
          !prevEndsWithSpaceOrPunct &&
          !currentStartsWithSpaceOrPunct &&
          currentText.trim();
      }
    }

    const normalizedColor =
      typeof span?.color === "string" ? span.color.trim().toLowerCase() : "";
    const colorStyle = HEX_COLOR_RE.test(normalizedColor) ? normalizedColor : undefined;

    const commonStyle = {
      fontWeight: span?.bold ? "bold" : undefined,
      fontStyle: span?.italic ? "italic" : undefined,
      textDecoration: span?.underline ? "underline" : undefined,
      color: colorStyle,
      whiteSpace: "pre-line",
    };

    const renderTextWithMarkers = (text, fragmentKeyPrefix) => {
      const thaiContext = !!(
        thaiColor &&
        (
          TH_RE.test(currentText) ||
          TH_RE.test(typeof collapsedInlines[m - 1]?.cleanText === "string" ? collapsedInlines[m - 1].cleanText : "") ||
          TH_RE.test(typeof collapsedInlines[m + 1]?.cleanText === "string" ? collapsedInlines[m + 1].cleanText : "")
        )
      );
      const inThaiZone = thaiZoneStartIndex >= 0 && m >= thaiZoneStartIndex;
      const segments = String(text).split(INLINE_MARKER_RE).filter((part) => part !== "");

      return segments.flatMap((segment, segIdx) => {
        const markerColor = INLINE_MARKER_COLORS[segment];
        if (markerColor) {
          const markerStyle = {
            ...commonStyle,
            color: markerColor,
            fontWeight: 600,
          };
          if (span?.link) {
            return (
              <a
                key={`${fragmentKeyPrefix}-marker-${segIdx}`}
                href={normalizeHref(span.link)}
                target="_blank"
                rel="noopener noreferrer"
                style={markerStyle}
              >
                {markerLabelFor(segment)}
              </a>
            );
          }
          return (
            <span key={`${fragmentKeyPrefix}-marker-${segIdx}`} style={markerStyle}>
              {markerLabelFor(segment)}
            </span>
          );
        }

        const segmentHasThai = !!(
          thaiColor &&
          (lineIsThaiOverride
            ? true
            : (strictThaiSplit
                ? TH_RE.test(segment)
                : (inThaiZone || thaiContext || TH_RE.test(segment))))
        );
        const segmentParts = segmentHasThai
          ? segment.split(/([\u0E00-\u0E7F]+|[.,!?;:'"(){}[\]<>\\\/\-–—…]+)/)
          : [segment];

        return segmentParts
          .filter((part) => part !== "")
          .map((part, idx) => {
            const prev = segmentParts[idx - 1] || "";
            const next = segmentParts[idx + 1] || "";
            const isPunctOnly = TH_PUNCT_ONLY_RE.test(part);
            const isNumericOnly = /^\d+(?:[.,]\d+)?$/.test(part);
            const adjacentThai = TH_RE.test(prev) || TH_RE.test(next);
            const partHasThai = lineIsThaiOverride
              ? true
              : (strictThaiSplit
                  ? (TH_RE.test(part) || ((isPunctOnly || isNumericOnly) && adjacentThai))
                  : (inThaiZone ||
                      TH_RE.test(part) ||
                      (segmentHasThai && (isPunctOnly || isNumericOnly) && adjacentThai)));

            const style = {
              ...commonStyle,
              color:
                colorStyle ||
                (partHasThai && thaiColor ? thaiColor : (englishColor || undefined)),
              fontWeight:
                partHasThai && thaiColor
                  ? (span?.bold ? 500 : 400)
                  : commonStyle.fontWeight,
            };

            if (span?.link) {
              const linkStyle = {
                ...style,
                color: span?.underline ? "#676769" : style.color,
              };
              return (
                <a
                  key={`${fragmentKeyPrefix}-frag-${segIdx}-${idx}`}
                  href={normalizeHref(span.link)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={linkStyle}
                >
                  {part}
                </a>
              );
            }

            return (
              <span key={`${fragmentKeyPrefix}-frag-${segIdx}-${idx}`} style={style}>
                {part}
              </span>
            );
          });
      });
    };

    return (
      <React.Fragment key={`${keyPrefix}-${m}`}>
        {needsSpaceBefore && " "}
        {renderTextWithMarkers(currentText, `${keyPrefix}-frag-${m}`)}
      </React.Fragment>
    );
  });
}
