import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const GA_MEASUREMENT_ID = "G-CTGR8YXB6G";

function Analytics() {
  const location = useLocation();

  useEffect(() => {
    if (typeof window === "undefined" || !window.gtag) {
      return;
    }

    window.gtag("config", GA_MEASUREMENT_ID, {
      page_path: location.pathname + location.search,
      page_title: document.title,
    });
  }, [location]);

  return null;
}

export default Analytics;
