import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import supabaseClient from "../supabaseClient";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";
import PlanNotice from "../Components/PlanNotice";
import "../Styles/LessonsIndex.css";
import "../Styles/LessonNavigationBanner.css";

const stageClassMap = {
  Beginner: "level-buttons-Beginner",
  Intermediate: "level-buttons-Intermediate",
  Advanced: "level-buttons-Advanced",
  Expert: "level-buttons-Expert",
};

const LessonsIndex = () => {
  const [isBackstoryOpen, setIsBackstoryOpen] = useState(false);
  const [lessons, setLessons] = useState([]);
  const [levels, setLevels] = useState([]);
  const location = useLocation();

  const [selectedStage, setSelectedStage] = useState(() => {
    if (typeof window === "undefined") return "Beginner";
    const stored = localStorage.getItem("lessonLibraryStage");
    return stored && stageClassMap[stored] ? stored : "Beginner";
  });
  const [selectedLevel, setSelectedLevel] = useState(() => {
    if (typeof window === "undefined") return 1;
    const stored = Number(localStorage.getItem("lessonLibraryLevel"));
    return Number.isFinite(stored) && stored > 0 ? stored : 1;
  });
  const [completedLessons, setCompletedLessons] = useState([]);
  const [levelCompletionStatus, setLevelCompletionStatus] = useState(null);
  const [profile, setProfile] = useState(null);
  const [allLessons, setAllLessons] = useState([]); // Store all lessons for first lesson calculation
  const [isMobileLayout, setIsMobileLayout] = useState(false);
  const [isMobileStageOpen, setIsMobileStageOpen] = useState(false);
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  // Track whether the stage has just changed
  const isStageChanged = useRef(false);

  // Fetch user profile (is_paid status)
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!user) {
        setProfile(null);
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("users")
          .select("is_paid")
          .eq("id", user.id)
          .single();

        if (error) {
          console.error("Error fetching user profile:", error.message);
          setProfile(null);
        } else {
          setProfile(data);
        }
      } catch (error) {
        console.error("Error fetching user profile:", error);
        setProfile(null);
      }
    };

    fetchUserProfile();
  }, [user]);

  // Fetch all lessons to determine first lessons of each level
  useEffect(() => {
    const fetchAllLessons = async () => {
      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("*")
          .order("stage", { ascending: true })
          .order("level", { ascending: true })
          .order("lesson_order", { ascending: true });

        if (error) throw error;
        setAllLessons(data || []);
      } catch (error) {
        console.error("Error fetching all lessons:", error.message);
      }
    };

    fetchAllLessons();
  }, []);

  // Calculate first lessons of each level
  const getFirstLessons = () => {
    const lessonsByLevel = {};

    allLessons.forEach((lesson) => {
      const levelKey = `${lesson.stage}-${lesson.level}`;
      if (!lessonsByLevel[levelKey]) {
        lessonsByLevel[levelKey] = [];
      }
      lessonsByLevel[levelKey].push(lesson);
    });

    const firstLessonIds = Object.values(lessonsByLevel)
      .map((levelLessons) => {
        const sorted = levelLessons.sort((a, b) => a.lesson_order - b.lesson_order);
        return sorted[0]?.id;
      })
      .filter(Boolean);

    return firstLessonIds;
  };

  // Determine if a lesson should show a lock icon
  const shouldShowLock = (lesson) => {
    // Not logged in → show lock
    if (!user) {
      return true;
    }

    // Paid user → no lock
    if (profile?.is_paid) {
      return false;
    }

    // Free user → lock all except first lesson of each level
    const firstLessons = getFirstLessons();
    return !firstLessons.includes(lesson.id);
  };

  const currentLevelIndex = levels.findIndex((lvl) => lvl === selectedLevel);
  const prevLevel = currentLevelIndex > 0 ? levels[currentLevelIndex - 1] : null;
  const nextLevel =
    currentLevelIndex !== -1 && currentLevelIndex < levels.length - 1
      ? levels[currentLevelIndex + 1]
      : null;

  const scrollToTop = useCallback(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, []);

  // Fetch levels for the selected stage
  useEffect(() => {
    const fetchLevels = async () => {
      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("level")
          .eq("stage", selectedStage)
          .order("level", { ascending: true });

        if (error) throw error;

        // Extract unique levels for the selected stage
        const uniqueLevels = [...new Set(data.map((lesson) => lesson.level))];
        setLevels(uniqueLevels);

        // Automatically select the first level ONLY when the stage changes
        if (uniqueLevels.length > 0 && isStageChanged.current) {
          setSelectedLevel(uniqueLevels[0]); // Set the first level of the new stage
          isStageChanged.current = false; // Reset the flag
        }

        if (uniqueLevels.length > 0 && !uniqueLevels.includes(selectedLevel)) {
          setSelectedLevel(uniqueLevels[0]);
        }
      } catch (error) {
        console.error("Error fetching levels:", error.message);
      }
    };

    fetchLevels();
  }, [selectedStage, selectedLevel, scrollToTop]); // Fetch levels whenever selectedStage changes

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const stageParam = params.get("stage");
    const levelParam = params.get("level");
    const normalizedStage =
      stageParam && stageClassMap[stageParam] ? stageParam : null;
    const normalizedLevel = levelParam ? Number(levelParam) : null;

    if (normalizedStage) {
      isStageChanged.current = false;
      setSelectedStage(normalizedStage);
    }
    if (Number.isFinite(normalizedLevel) && normalizedLevel > 0) {
      setSelectedLevel(normalizedLevel);
    }
  }, [location.search]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem("lessonLibraryStage", selectedStage);
    localStorage.setItem("lessonLibraryLevel", String(selectedLevel));
  }, [selectedStage, selectedLevel]);

  // Fetch completed lessons for the authenticated user
  useEffect(() => {
    const fetchCompletedLessons = async () => {
      if (!user) {
        setCompletedLessons([]);
        return;
      }

      try {
        // Get the current session to access the access token
        const { data: { session } } = await supabaseClient.auth.getSession();

        if (!session?.access_token) {
          setCompletedLessons([]);
          return;
        }

        // Make API call to backend for completed lessons
        const response = await fetch(`${API_BASE_URL}/api/user/completed-lessons`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setCompletedLessons(data.completed_lessons || []);
        }
      } catch (error) {
        console.error('Error fetching completed lessons:', error);
        setCompletedLessons([]);
      }
    };

    fetchCompletedLessons();
  }, [user]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 480px)");
    const handler = (e) => setIsMobileLayout(e.matches);
    handler(mq);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Fetch level completion status for the current stage and level
  useEffect(() => {
    const fetchLevelCompletionStatus = async () => {
      if (!user || !selectedStage || !selectedLevel) {
        setLevelCompletionStatus(null);
        return;
      }

      try {
        // Get the current session to access the access token
        const { data: { session } } = await supabaseClient.auth.getSession();

        if (!session?.access_token) {
          setLevelCompletionStatus(null);
          return;
        }

        // Make API call to check level completion status
        const response = await fetch(`${API_BASE_URL}/api/user/level-completion-status/${selectedStage}/${selectedLevel}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setLevelCompletionStatus(data);
        } else {
          setLevelCompletionStatus(null);
        }
      } catch (error) {
        console.error('Error fetching level completion status:', error);
        setLevelCompletionStatus(null);
      }
    };

    fetchLevelCompletionStatus();
  }, [user, selectedStage, selectedLevel]);

  // Fetch lessons for the selected stage and level
  useEffect(() => {
    const fetchLessons = async () => {
      if (!selectedLevel) return; // Don't fetch if no level is selected

      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("*")
          .eq("stage", selectedStage)
          .eq("level", selectedLevel)
          .order("lesson_order", { ascending: true });

        if (error) throw error;
        setLessons(data || []);
      } catch (error) {
        console.error("Error fetching lessons:", error.message);
      }
    };

    fetchLessons();
  }, [selectedStage, selectedLevel]); // Fetch lessons whenever selectedStage or selectedLevel changes

  // Handle stage change
  const handleStageChange = (stage) => {
    setSelectedStage(stage);
    isStageChanged.current = true; // Set the flag to indicate a stage change
    if (!isMobileLayout) {
      scrollToTop();
    }
  };

  const handleLevelSelect = (level) => {
    setSelectedLevel(level);
    if (!isMobileLayout) {
      scrollToTop();
    }
  };

  // Helper function to check if a lesson is completed
  const isLessonCompleted = (lessonId) => {
    return completedLessons.some(completed => completed.lesson_id === lessonId);
  };

  const sortedLessons = [
    ...lessons.filter((l) => !(l.title || "").toLowerCase().includes("checkpoint")),
    ...lessons.filter((l) => (l.title || "").toLowerCase().includes("checkpoint")),
  ];

  const pickUiLang = useCallback(
    (en, th) => {
      if (uiLang === "th") {
        return th || en || "";
      }
      return en || th || "";
    },
    [uiLang]
  );

  const stages = ["Beginner", "Intermediate", "Advanced", "Expert"];

  const { levelCompletionMap, stageCompletionMap } = useMemo(() => {
    const completionIds = new Set(
      (completedLessons || [])
        .map((entry) => entry.lesson_id || entry.lessons?.id)
        .filter(Boolean)
    );

    const levelAggregates = {};
    const stageAggregates = {};

    (allLessons || []).forEach((lesson) => {
      if (!lesson) return;
      const { id, stage, level } = lesson;
      if (!stage || typeof level === "undefined" || level === null) {
        return;
      }

      const levelKey = `${stage}-${level}`;
      if (!levelAggregates[levelKey]) {
        levelAggregates[levelKey] = { total: 0, completed: 0 };
      }
      levelAggregates[levelKey].total += 1;
      if (id && completionIds.has(id)) {
        levelAggregates[levelKey].completed += 1;
      }

      if (!stageAggregates[stage]) {
        stageAggregates[stage] = { total: 0, completed: 0 };
      }
      stageAggregates[stage].total += 1;
      if (id && completionIds.has(id)) {
        stageAggregates[stage].completed += 1;
      }
    });

    const levelCompletion = {};
    Object.entries(levelAggregates).forEach(([key, counts]) => {
      levelCompletion[key] = counts.total > 0 && counts.completed >= counts.total;
    });

    const stageCompletion = {};
    Object.entries(stageAggregates).forEach(([key, counts]) => {
      stageCompletion[key] = counts.total > 0 && counts.completed >= counts.total;
    });

    return {
      levelCompletionMap: levelCompletion,
      stageCompletionMap: stageCompletion,
    };
  }, [allLessons, completedLessons]);

  const handleLessonClick = (event) => {
    if (selectedStage === "Expert") {
      event.preventDefault();
    }
  };

  return (
    <div className="lessons-index-page-container">
      <header className="lessons-index-page-header">
        <h1 className="page-header-text">{t("lessonLibraryPage.title", uiLang)}</h1>
        <p className="lessons-index-page-header-subtitle">
          {t("lessonLibraryPage.subtitle", uiLang)}
        </p>
      </header>
      <div className="lesson-library">
        {!user && (
          <PlanNotice
            heading="Unlock our full Lesson Library."
            subtext={
              <>
                All our lessons are locked. Create a free account to access our{" "}
                <Link to="/free-lessons">free lessons</Link>, or become a member for full access to over 150 lessons!
              </>
            }
            cta={{
              label: "SIGN UP FOR FREE",
              to: "/signup",
            }}
            secondaryCta={{
              label: "BECOME A MEMBER",
              to: "/membership",
            }}
            footerNote={
              <>
                <span>Not ready to create an account?</span>
                <span>
                  <Link to="/try-lessons">Click here</Link> to try 4 free lessons, no sign-up required!
                </span>
              </>
            }
          />
        )}
        {user && profile?.is_paid === false && (
          <PlanNotice
            heading="You're on our free plan."
            subtext={[
              <>
                <Link to="/membership">Upgrade</Link> to enjoy access to our full lesson library.
              </>,
              <>
                Or, explore the lessons available to you in our{" "}
                <Link to="/free-lessons">free lesson library</Link>.
              </>,
            ]}
          />
        )}
        {/* The level buttons and placement test header */}
        <div className="stages-levels-subtitle">
          {isMobileLayout ? (
            <>
              <div className="mobile-stage-selector">
                <button
                  type="button"
                  className="mobile-stage-toggle"
                  onClick={() => setIsMobileStageOpen((prev) => !prev)}
                  aria-expanded={isMobileStageOpen}
                >
                  <span>{selectedStage.toUpperCase()}</span>
                  <span className="mobile-stage-caret">▾</span>
                </button>
                {isMobileStageOpen && (
                  <div className="mobile-stage-list">
                    {stages.map((stage) => (
                      <button
                        key={`mobile-stage-${stage}`}
                        type="button"
                        className={`mobile-stage-item${selectedStage === stage ? " is-active" : ""}`}
                        onClick={() => {
                          handleStageChange(stage);
                          setIsMobileStageOpen(false);
                        }}
                      >
                        <span>{stage.toUpperCase()}</span>
                        {stageCompletionMap[stage] && (
                          <span className="completion-checkmark" aria-hidden="true">
                            ✓
                          </span>
                        )}
                        {stage === "Expert" && (
                          <span className="stage-coming-soon-inline">Coming Soon!</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="mobile-level-buttons">
                {levels.map((lvl) => (
                  <button
                    key={`mobile-level-${lvl}`}
                    className={`mobile-level-btn ${selectedLevel === lvl ? "active" : ""}`}
                    onClick={() => handleLevelSelect(lvl)}
                  >
                    LEVEL {lvl}
                    {levelCompletionMap[`${selectedStage}-${lvl}`] && (
                      <span className="completion-checkmark" aria-hidden="true">
                        ✓
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="lesson-stages">
                {stages.map((stage) => (
                  <div className="stage-btn-wrapper" key={stage}>
                    <button
                      className={`stage-btn ${selectedStage === stage ? "active" : ""}`}
                      onClick={() => handleStageChange(stage)}
                    >
                      {stage.toUpperCase()}
                      {stageCompletionMap[stage] && (
                        <span className="completion-checkmark" aria-hidden="true">
                          ✓
                        </span>
                      )}
                    </button>
                    {stage === "Expert" && (
                      <span className="stage-coming-soon-badge">COMING SOON!</span>
                    )}
                  </div>
                ))}
              </div>

              <div
                className={`level-buttons ${stageClassMap[selectedStage] || stageClassMap.Beginner}`}
              >
                {levels.map((lvl) => (
                  <button
                    key={lvl}
                    className={`level-btn ${selectedLevel === lvl ? "active" : ""}`}
                    onClick={() => handleLevelSelect(lvl)}
                  >
                    LEVEL {lvl}
                    {levelCompletionMap[`${selectedStage}-${lvl}`] && (
                      <span className="completion-checkmark" aria-hidden="true">
                        ✓
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Render lessons */}
        <div className="level-wrapper">
          <div className="level-container">
            <section className="level-backstory">
              <div className={`level-header ${isBackstoryOpen ? "backstory-open" : ""}`} onClick={() => setIsBackstoryOpen(!isBackstoryOpen)}>
                <div className="level-text-graphic">
                  <div className="level-title-group">
                    <span className="level-header-text">
                      LEVEL {selectedLevel}
                    </span>
                    {levelCompletionStatus?.is_completed && (
                      <span className="level-complete-badge">
                        LEVEL COMPLETE <span role="img" aria-label="Party popper">🎉</span>
                      </span>
                    )}
                  </div>
                  <img src="/images/red-level-icon-clipboard.webp" alt="Red Clipboard" className="level-header-image" />
                </div>

                <div className="backstory-arrow-group">
                  <span className="backstory-header-text">{isBackstoryOpen ? "HIDE BACKSTORY" : "VIEW BACKSTORY"}</span>
                </div>
              </div>

              <div className={`backstory-container ${isBackstoryOpen ? "open" : ""}`}>
                {isBackstoryOpen && (
                  <div className="backstory-content">
                    <span>Pailin has just moved from Bangkok to Los Angeles. She's at a summer orientation for foreign exchange students at University of California, Los Angeles, where she will be meeting other foreign exchange students and will be learning more about the program.</span>
                  </div>
                )}
              </div>
            </section>

            <div className="level-content">
              <div className="lesson-list">
                {sortedLessons.map((lesson) => {
                  const lessonCompleted = isLessonCompleted(lesson.id);
                  return (
                    <Link
                      to={`/lesson/${lesson.id}`}
                      key={lesson.id}
                      className="lesson-item"
                      onClick={handleLessonClick}
                    >
                      <div className="lesson-item-left">
                        <div className="lesson-index-slot">
                          {(lesson.title || "").toLowerCase().includes("checkpoint") ? (
                            <img src="/images/black-checkmark-level-checkpoint.webp" alt="Lesson Checkpoint" className="level-checkmark" />
                          ) : (
                            <span className="lesson-number">{lesson.level}.{lesson.lesson_order}</span>
                          )}
                        </div>
                        <div className="name-desc-container">
                          <span className="lesson-name">
                            {pickUiLang(lesson.title, lesson.title_th)}
                          </span>
                          {(lesson.focus || lesson.focus_th) && (
                            <span className="lesson-focus">
                              {pickUiLang(lesson.focus, lesson.focus_th)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="lesson-item-right">
                        {shouldShowLock(lesson) ? (
                          <img
                            src="/images/lock.webp"
                            alt="Locked"
                            className="lesson-lock-icon"
                          />
                        ) : lessonCompleted ? (
                          <img
                            src="/images/filled-checkmark-lesson-complete.webp"
                            alt="Completed"
                            className="checkmark-img checkmark-completed"
                          />
                        ) : null}
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        <div className="level-navigation-row">
          <div className="level-nav-left">
            {prevLevel !== null ? (
              <button
                type="button"
                className="lesson-navigation-text prev level-nav-button"
                onClick={() => handleLevelSelect(prevLevel)}
                aria-label={`Go to level ${prevLevel}`}
              >
                ← LEVEL {prevLevel}
              </button>
            ) : (
              <span className="lesson-navigation-text prev disabled" aria-hidden="true">
                ← LEVEL {selectedLevel}
              </span>
            )}
          </div>
          <div className="level-nav-right">
            {nextLevel !== null ? (
              <button
                type="button"
                className="lesson-navigation-text next level-nav-button"
                onClick={() => handleLevelSelect(nextLevel)}
                aria-label={`Go to level ${nextLevel}`}
              >
                LEVEL {nextLevel} →
              </button>
            ) : (
              <span className="lesson-navigation-text next disabled" aria-hidden="true">
                LEVEL {selectedLevel} →
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LessonsIndex;
