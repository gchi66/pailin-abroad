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

function renderInlines(inlines = []) {
  return inlines.map((span, idx) => {
    const text = cleanAudioTags(span?.text || "");
    const style = {
      fontWeight: span?.bold ? "700" : undefined,
      fontStyle: span?.italic ? "italic" : undefined,
      textDecoration: span?.underline ? "underline" : undefined,
      whiteSpace: "pre-line",
    };
    return (
      <React.Fragment key={idx}>
        {idx > 0 && !/^[\s.,!?;:'"()\[\]\-]/.test(text) ? " " : ""}
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
    return sorted;
  }, [nodes]);

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
                aria-disabled={isLocked || undefined}
              >
                {hasSnippet ? (
                  <AudioButton
                    node={node}
                    audioIndex={audioIndex}
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
