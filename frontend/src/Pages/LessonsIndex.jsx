import React, { useState, useEffect, useRef } from "react";
import supabaseClient from "../supabaseClient";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { API_BASE_URL } from "../config/api";
import "../Styles/LessonsIndex.css";

const LessonsIndex = () => {
  const [isBackstoryOpen, setIsBackstoryOpen] = useState(false);
  const [lessons, setLessons] = useState([]);
  const [levels, setLevels] = useState([]);
  const [selectedStage, setSelectedStage] = useState("Beginner");
  const [selectedLevel, setSelectedLevel] = useState(1);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [levelCompletionStatus, setLevelCompletionStatus] = useState(null);
  const [profile, setProfile] = useState(null);
  const [allLessons, setAllLessons] = useState([]); // Store all lessons for first lesson calculation
  const { user } = useAuth();

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
      } catch (error) {
        console.error("Error fetching levels:", error.message);
      }
    };

    fetchLevels();
  }, [selectedStage]); // Fetch levels whenever selectedStage changes

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
      } catch (error) {
        console.error("Error fetching levels:", error.message);
      }
    };

    fetchLevels();
  }, [selectedStage]); // Fetch levels whenever selectedStage changes

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
  };

  // Helper function to check if a lesson is completed
  const isLessonCompleted = (lessonId) => {
    return completedLessons.some(completed => completed.lesson_id === lessonId);
  };

  const sortedLessons = [
    ...lessons.filter((l) => !(l.title || "").toLowerCase().includes("checkpoint")),
    ...lessons.filter((l) => (l.title || "").toLowerCase().includes("checkpoint")),
  ];

  return (
    <div className="lessons-index-page-container">
      <header className="lessons-index-page-header">
        <h1 className="page-header-text">LESSON LIBRARY</h1>
        <p className="lessons-index-page-header-subtitle">Over 150 conversation-based lessons to improve your English</p>
      </header>
      <div className="lesson-library">
        {/* The level buttons and placement test header */}
        <div className="stages-levels-subtitle">
          <p className="lesson-subtitle">
            Not sure where to start? Take our <button type="button" className="placement-test-link">Free Placement Test</button>.
          </p>

          <div className="lesson-stages">
            <button
              className={`stage-btn ${selectedStage === "Beginner" ? "active" : ""}`}
              onClick={() => handleStageChange("Beginner")}
            >
              BEGINNER
            </button>
            <button
              className={`stage-btn ${selectedStage === "Intermediate" ? "active" : ""}`}
              onClick={() => handleStageChange("Intermediate")}
            >
              INTERMEDIATE
            </button>
            <button
              className={`stage-btn ${selectedStage === "Advanced" ? "active" : ""}`}
              onClick={() => handleStageChange("Advanced")}
            >
              ADVANCED
            </button>
            <button
              className={`stage-btn ${selectedStage === "Expert" ? "active" : ""}`}
              onClick={() => handleStageChange("Expert")}
            >
              EXPERT
            </button>
          </div>

          {/* Level buttons */}
          <div className={`level-btns-${selectedStage.replace(/\s+/g, "")}`}>
            {levels.map((lvl) => (
              <button
                key={lvl}
                className={`level-btn ${selectedLevel === lvl ? "active" : ""}`}
                onClick={() => setSelectedLevel(lvl)}
              >
                LEVEL {lvl}
              </button>
            ))}
          </div>
        </div>

        {/* Render lessons */}
        <div className="level-wrapper">
          <div className="level-container">
            <section className="level-backstory">
              <div className={`level-header ${isBackstoryOpen ? "backstory-open" : ""}`} onClick={() => setIsBackstoryOpen(!isBackstoryOpen)}>
                <div className="level-text-graphic">
                  <span className="level-header-text">LEVEL {selectedLevel}</span>
                  <img src="/images/red-level-icon-clipboard.webp" alt="Red Clipboard" className="level-header-image" />
                </div>

                <div className="backstory-arrow-group">
                  <span className="backstory-header-text">{isBackstoryOpen ? "HIDE BACKSTORY" : "VIEW BACKSTORY"}</span>
                  <img
                    src={isBackstoryOpen ? "/images/collapse-collapsible-box.webp" : "/images/expand-collapsible-box.webp"}
                    alt={isBackstoryOpen ? "Collapse backstory" : "Expand backstory"}
                    className="backstory-arrow-icon"
                  />
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
                {sortedLessons.map((lesson) => (
                  <Link to={`/lesson/${lesson.id}`} key={lesson.id} className="lesson-item">
                    <div className="lesson-item-left">
                      {(lesson.title || "").toLowerCase().includes("checkpoint") ? (
                        <img src="/images/black-checkmark-level-checkpoint.webp" alt="Lesson Checkpoint" className="level-checkmark" />
                      ) : (
                        <span className="lesson-number">{lesson.level}.{lesson.lesson_order}</span>
                      )}
                      <div className="name-desc-container">
                        <span className="lesson-name">
                          {lesson.title}
                        </span>
                        {lesson.focus && (
                          <span className="lesson-focus">
                            {lesson.focus}
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
                      ) : (
                        <img
                          src={isLessonCompleted(lesson.id) ? "/images/filled-checkmark-lesson-complete.webp" : "/images/CheckCircle.png"}
                          alt={isLessonCompleted(lesson.id) ? "Completed" : "Not completed"}
                          className={`checkmark-img ${isLessonCompleted(lesson.id) ? "checkmark-completed" : ""}`}
                        />
                      )}
                    </div>
                  </Link>
                ))}
              </div>
              <div className={`mark-finished-row ${levelCompletionStatus?.is_completed ? 'completed' : ''}`}>
                <span className="mark-finished-content">
                  {levelCompletionStatus?.is_completed ? (
                    <>
                      <span className="mark-finished-text">LEVEL {selectedLevel} COMPLETED</span>
                      <img src="/images/filled-checkmark-lesson-complete.webp" alt="Completed" className="checkmark-img checkmark-completed" />
                    </>
                  ) : (
                    <>
                      <span className="mark-finished-text">MARK LEVEL {selectedLevel} AS FINISHED</span>
                      <img src="/images/CheckCircle.png" alt="Not completed" className="checkmark-img" />
                    </>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LessonsIndex;
