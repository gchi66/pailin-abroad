import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";
import "../Styles/LegalPage.css";

const LegalPage = ({ title, slug }) => {
  const { ui } = useUiLang();
  const legalCopy = copy.legal;
  const [markdown, setMarkdown] = useState("");
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let isActive = true;
    const buildPath = (lang) => `${process.env.PUBLIC_URL}/legal/${slug}.${lang}.md`;

    const loadMarkdown = async () => {
      setStatus("loading");
      try {
        const response = await fetch(buildPath(ui));
        if (response.ok) {
          const text = await response.text();
          if (isActive) {
            setMarkdown(text);
            setStatus("ready");
          }
          return;
        }

        const fallbackResponse = await fetch(buildPath("en"));
        if (!fallbackResponse.ok) throw new Error("Missing legal content");
        const fallbackText = await fallbackResponse.text();
        if (isActive) {
          setMarkdown(fallbackText);
          setStatus("ready");
        }
      } catch (error) {
        if (isActive) {
          setMarkdown("");
          setStatus("error");
        }
      }
    };

    loadMarkdown();
    return () => {
      isActive = false;
    };
  }, [slug, ui]);

  return (
    <main className="legal-page">
      <header className="legal-header">
        <h1>{title}</h1>
        {status === "loading" && (
          <p className="legal-status">{pick(legalCopy.loading, ui)}</p>
        )}
        {status === "error" && (
          <p className="legal-status legal-status--error">
            {pick(legalCopy.missing, ui)}
          </p>
        )}
      </header>
      {status === "ready" && (
        <div className="legal-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            rehypePlugins={[rehypeRaw]}
          >
            {markdown}
          </ReactMarkdown>
        </div>
      )}
    </main>
  );
};

export default LegalPage;
