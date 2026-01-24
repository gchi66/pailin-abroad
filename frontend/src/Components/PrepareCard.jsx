import React, { useMemo } from "react";
import AudioButton from "./AudioButton";
import "../Styles/PrepareCard.css";
import { copy, pick } from "../ui-lang/i18n";

// Lightweight inline renderer (keeps style spacing and drops [audio:...] tags)
function cleanAudioTags(text) {
  if (!text || typeof text !== "string") return text;
  return text
    .replace(/\[audio:[^\]]+\]/g, " ")
    .replace(/[^\S\r\n]+/g, " ")
    .replace(/\s*\n\s*/g, "\n");
}

const TH_RE = /[\u0E00-\u0E7F]/;

function renderInlines(inlines = []) {
  const processed = (inlines || []).map((span) => {
    const text = cleanAudioTags(span?.text || "");
    const originalHadTrailingSpace =
      typeof span?.text === "string" && /[ \t]+$/.test(span.text);
    return { span, text, originalHadTrailingSpace };
  });

  return processed.map((entry, idx) => {
    const { span, text } = entry;
    const style = {
      fontWeight: span?.bold ? "700" : undefined,
      fontStyle: span?.italic ? "italic" : undefined,
      textDecoration: span?.underline ? "underline" : undefined,
      whiteSpace: "pre-line",
    };
    let needsSpaceBefore = false;
    if (idx > 0) {
      const prev = processed[idx - 1];
      const prevText = prev.text || "";
      const currentText = text || "";
      const prevEndsWithSpaceOrPunct =
        /[\s.,!?;:'"()[\]\-]$/.test(prevText);
      const currentStartsWithSpaceOrPunct =
        /^[\s.,!?;:'"()[\]\-]/.test(currentText);
      const prevEndsWithWordChar = /[A-Za-z0-9]$/.test(prevText);
      const currentStartsWithWordChar = /^[A-Za-z0-9]/.test(currentText);
      const hasThaiBoundary =
        TH_RE.test(prevText) || TH_RE.test(currentText);
      const looksLikeSplitWord =
        prevEndsWithWordChar && currentStartsWithWordChar;

      needsSpaceBefore =
        !hasThaiBoundary &&
        !(looksLikeSplitWord && !prev.originalHadTrailingSpace) &&
        !prevEndsWithSpaceOrPunct &&
        !currentStartsWithSpaceOrPunct &&
        currentText.trim();
    }
    return (
      <React.Fragment key={idx}>
        {needsSpaceBefore ? " " : ""}
        <span style={style}>{text}</span>
      </React.Fragment>
    );
  });
}

export default function PrepareCard({
  section,
  audioIndex,
  uiLang = "en",
  isLocked = false,
}) {
  const nodes = useMemo(() => {
    if (!section) return [];
    const raw = section.content_jsonb;
    if (Array.isArray(raw)) return raw;
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [section]);

  const items = useMemo(() => {
    const sorted = [...nodes].sort((a, b) => {
      const aSeq = Number(a?.audio_seq) || 0;
      const bSeq = Number(b?.audio_seq) || 0;
      if (aSeq !== bSeq) return aSeq - bSeq;
      return 0;
    });
    const filtered = sorted.filter((node) => {
      const inlines = Array.isArray(node?.inlines) ? node.inlines : [];
      const text = cleanAudioTags(
        inlines
          .map((span) => (span && typeof span.text === "string" ? span.text : ""))
          .join("")
      ).trim();
      const hasSnippet =
        !!(node?.audio_key && audioIndex?.by_key?.[node.audio_key]) ||
        !!(
          node?.audio_section &&
          node?.audio_seq &&
          audioIndex?.[node.audio_section]?.[node.audio_seq]
        );
      return text.length > 0 || hasSnippet;
    });
    return filtered;
  }, [nodes, audioIndex]);

  if (!section || items.length === 0) return null;

  const title = pick(copy.prepareCard.title, uiLang) || "BEFORE YOU LISTEN";
  const subtitle =
    pick(copy.prepareCard.subtitle, uiLang) ||
    "Get familiar with the words you'll hear in the conversation.";

  return (
    <section className="lc-card prepare-card">
      <header className="lc-head prepare-head">
        <div className="prepare-head-left">
          <span className="prepare-title">{title}</span>
          <span className="prepare-subtitle">{subtitle}</span>
        </div>
      </header>
      <div className="prepare-body">
        <ul className="prepare-grid">
          {items.map((node, idx) => {
            const indent = Number(node?.indent) || 0;
            const style = indent
              ? { paddingLeft: `${1.2 * indent}rem` }
              : undefined;
            const itemStyle = {
              ...style,
              pointerEvents: isLocked ? "none" : undefined,
            };

            const hasSnippet =
              !!(node?.audio_key && audioIndex?.by_key?.[node.audio_key]) ||
              !!(
                node?.audio_section &&
                node?.audio_seq &&
                audioIndex?.[node.audio_section]?.[node.audio_seq]
              );

            return (
              <li
                key={node.audio_seq ? `prep-${node.audio_seq}` : `prep-${idx}`}
                className={`prepare-item ${isLocked ? "prepare-item-locked" : ""}`}
                style={itemStyle}
              >
                {hasSnippet ? (
                  <AudioButton
                    node={node}
                    audioIndex={audioIndex}
                    preload
                    size={1.4}
                    className="prepare-audio-button"
                  />
                ) : (
                  <span className="prepare-audio-placeholder" aria-hidden>
                    ▶
                  </span>
                )}
                <div className="prepare-text">{renderInlines(node.inlines || [])}</div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
