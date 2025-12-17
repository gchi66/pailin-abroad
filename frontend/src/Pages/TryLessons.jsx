import React from "react";
import { useNavigate } from "react-router-dom";
import PlanNotice from "../Components/PlanNotice";
import { useAuth } from "../AuthContext";
import "../Styles/TryLessons.css";
import FreeLessonCards from "../Components/FreeLessonCards";
import MembershipFeatures from "../Components/MembershipFeatures";
import SignUpCTA from "../Components/SignUpCTA";

const TryLessons = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const handleSignupClick = () => navigate("/signup");

  return (
    <div className="try-lessons-page-container">
      {/* Header */}
      <header className="try-lessons-page-header">
        <h1 className="try-lessons-header-text">Try Our Lessons</h1>
        <p className="try-lessons-header-subtitle">
          4 free lessons for you to try, no sign-up needed!
        </p>
      </header>

      {/* Intro Text */}
      <div className="try-lessons-intro-section">
        <p className="try-lessons-intro">
          We're confident you'll love our unique, narrative-driven method of learning English.
          Explore a lesson from each level to see for yourself.
        </p>
      </div>

      {/* Free Lesson Cards */}
      <div className="try-lessons-cards-container">
        <FreeLessonCards showHeader={false} />
      </div>

      <SignUpCTA onSignupClick={handleSignupClick} />

      <div className="try-lessons-plan-notice-wrapper">
        {!user ? (
          <PlanNotice
            heading="Ready to continue your journey?"
            subtext={[
              "You can create a free account to unlock our entire library of free lessons.",
            ]}
            cta={{
              label: "SIGN UP FOR FREE",
              to: "/signup",
            }}
            secondaryCta={{
              label: "BECOME A MEMBER",
              to: "/membership",
            }}
            ctaDivider={
              <>
                Or, get full access to <strong>all 150+ lessons</strong> and take your English to the next level with a full membership.
              </>
            }
          />
        ) : (
          <PlanNotice
            heading="Ready to continue your journey?"
            subtext={
              <>
                Get full access to <strong>all 150+ lessons</strong> and take your English to the next level with a full membership.
              </>
            }
            cta={{
              label: "BECOME A MEMBER",
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
