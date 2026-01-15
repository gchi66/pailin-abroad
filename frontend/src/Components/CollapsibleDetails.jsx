import { useEffect, useRef } from "react";

export default function CollapsibleDetails({
  defaultOpen = false,
  resetKey,
  className = "",
  summaryClassName = "markdown-summary",
  summaryContent,
  summaryProps = {},
  onToggle,
  children,
  ...rest
}) {
  const detailsRef = useRef(null);
  const initializedRef = useRef(false);
  const prevResetRef = useRef(resetKey);

  useEffect(() => {
    if (prevResetRef.current !== resetKey) {
      prevResetRef.current = resetKey;
      initializedRef.current = false;
    }

    if (initializedRef.current) return;

    if (defaultOpen && detailsRef.current && !detailsRef.current.open) {
      detailsRef.current.open = true;
    }

    initializedRef.current = true;
  }, [defaultOpen, resetKey]);

  const handleToggle = (event) => {
    if (typeof onToggle === "function") {
      onToggle(event.currentTarget.open);
    }
  };

  return (
    <details ref={detailsRef} className={className} onToggle={handleToggle} {...rest}>
      <summary className={summaryClassName} {...summaryProps}>
        {summaryContent}
      </summary>
      {children}
    </details>
  );
}
