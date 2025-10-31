import { useEffect, useRef } from "react";

export default function CollapsibleDetails({
  defaultOpen = false,
  className = "",
  summaryClassName = "markdown-summary",
  summaryContent,
  summaryProps = {},
  children,
  ...rest
}) {
  const detailsRef = useRef(null);
  const initializedRef = useRef(false);

  useEffect(() => {
    if (initializedRef.current) return;

    if (defaultOpen && detailsRef.current && !detailsRef.current.open) {
      detailsRef.current.open = true;
    }

    initializedRef.current = true;
  }, [defaultOpen]);

  return (
    <details ref={detailsRef} className={className} {...rest}>
      <summary className={summaryClassName} {...summaryProps}>
        {summaryContent}
      </summary>
      {children}
    </details>
  );
}
