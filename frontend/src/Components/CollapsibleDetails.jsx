import { useEffect, useRef } from "react";

export default function CollapsibleDetails({
  defaultOpen = false,
  resetKey,
  className = "",
  summaryClassName = "markdown-summary",
  summaryContent,
  summaryProps = {},
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

  return (
    <details ref={detailsRef} className={className} {...rest}>
      <summary className={summaryClassName} {...summaryProps}>
        {summaryContent}
      </summary>
      {children}
    </details>
  );
}
