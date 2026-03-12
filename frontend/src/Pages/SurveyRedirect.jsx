import { useEffect } from "react";

const SURVEY_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLSdRKKWnGiH9ggTcmPP1BAXihoOULcGZNL-NJkfHR6rtxvF-Ow/viewform?usp=sharing&ouid=105573501071345408343";

const SurveyRedirect = () => {
  useEffect(() => {
    window.location.replace(SURVEY_URL);
  }, []);

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h2>Redirecting to survey…</h2>
      <p>If nothing happens, open the survey in a new tab.</p>
      <p>
        <a href={SURVEY_URL} rel="noreferrer" target="_blank">
          Open survey
        </a>
      </p>
    </div>
  );
};

export default SurveyRedirect;
