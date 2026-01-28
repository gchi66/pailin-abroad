import React from "react";
import PlanNotice from "../Components/PlanNotice";
import { useAuth } from "../AuthContext";
import "../Styles/TryLessons.css";
import FreeLessonCards from "../Components/FreeLessonCards";
import MembershipFeatures from "../Components/MembershipFeatures";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

const TryLessons = () => {
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  return (
    <div className="try-lessons-page-container">
      {/* Header */}
      <header className="try-lessons-page-header">
        <h1 className="try-lessons-header-text">{t("tryLessonsPage.title", uiLang)}</h1>
        <p className="try-lessons-header-subtitle">
          {t("tryLessonsPage.subtitle", uiLang)}
        </p>
      </header>

      {/* Intro Text */}
      <div className="try-lessons-intro-section">
        <p className="try-lessons-intro">
          {t("tryLessonsPage.introLine1", uiLang)}{" "}
          {t("tryLessonsPage.introLine2", uiLang)}
        </p>
      </div>

      {/* Free Lesson Cards */}
      <div className="try-lessons-cards-container">
        <FreeLessonCards showHeader={false} />
      </div>

      <div className="try-lessons-plan-notice-wrapper">
        {!user ? (
          <PlanNotice
            heading={t("tryLessonsPage.planNotice.heading", uiLang)}
            subtext={[t("tryLessonsPage.planNotice.noAccountSubtext", uiLang)]}
            cta={{
              label: t("lessonsIndexPage.signUpFree", uiLang),
              to: "/signup",
            }}
            secondaryCta={{
              label: t("lessonsIndexPage.becomeMember", uiLang),
              to: "/membership",
            }}
            ctaDivider={
              <>
                {t("tryLessonsPage.planNotice.dividerPrefix", uiLang)}
                <strong>{t("tryLessonsPage.planNotice.dividerEm", uiLang)}</strong>
                {t("tryLessonsPage.planNotice.dividerSuffix", uiLang)}
              </>
            }
          />
        ) : (
          <PlanNotice
            heading={t("tryLessonsPage.planNotice.heading", uiLang)}
            subtext={
              <>
                {t("tryLessonsPage.planNotice.loggedInPrefix", uiLang)}
                <strong>{t("tryLessonsPage.planNotice.loggedInEm", uiLang)}</strong>
                {t("tryLessonsPage.planNotice.loggedInSuffix", uiLang)}
              </>
            }
            cta={{
              label: t("lessonsIndexPage.becomeMember", uiLang),
              to: "/membership",
            }}
          />
        )}
      </div>

      <MembershipFeatures />
    </div>
  );
};

export default TryLessons;
