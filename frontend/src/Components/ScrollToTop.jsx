import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const LESSON_ROUTE_PREFIX = "/lesson/";

const ScrollToTop = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    if (pathname.startsWith(LESSON_ROUTE_PREFIX)) return;

    // Defer scrolling until after layout updates to avoid jank on quick transitions.
    const frame = window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  return null;
};

export default ScrollToTop;
