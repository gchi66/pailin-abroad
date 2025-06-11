import React, { useState, useEffect, useRef } from "react";
import supabaseClient from "../supabaseClient";
import { Link } from "react-router-dom";
import "../Styles/LessonsIndex.css";

const LessonsIndex = () => {
  const [isBackstoryOpen, setIsBackstoryOpen] = useState(false);
  const [lessons, setLessons] = useState([]);
  const [levels, setLevels] = useState([]);
  const [selectedStage, setSelectedStage] = useState("Beginner");
  const [selectedLevel, setSelectedLevel] = useState(1);

  // Track whether the stage has just changed
  const isStageChanged = useRef(false);

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

  const sortedLessons = [
    ...lessons.filter((l) => !(l.title || "").toLowerCase().includes("checkpoint")),
    ...lessons.filter((l) => (l.title || "").toLowerCase().includes("checkpoint")),
  ];

  return (
    <div className="lessons-index-page-container">
      <header className="lessons-index-page-header">
        <h1 className="page-header-text">LESSON LIBRARY</h1>
        <img src="/images/books-lesson-library.webp" alt="Library Books" className="header-image" />
      </header>
      <div className="lesson-library">
        {/* The level buttons and placement test header */}
        <div className="stages-levels-subtitle">
          <p className="lesson-subtitle">
            Not sure where to start? Take our <a href="#">Free Placement Test</a>.
          </p>

          <div className="lesson-stages">
            <button
              className={`stage-btn ${selectedStage === "Beginner" ? "active" : ""}`}
              onClick={() => handleStageChange("Beginner")}
            >
              BEGINNER
            </button>
            <button
              className={`stage-btn ${selectedStage === "Lower Intermediate" ? "active" : ""}`}
              onClick={() => handleStageChange("Lower Intermediate")}
            >
              LOWER INTERMEDIATE
            </button>
            <button
              className={`stage-btn ${selectedStage === "Upper Intermediate" ? "active" : ""}`}
              onClick={() => handleStageChange("Upper Intermediate")}
            >
              UPPER INTERMEDIATE
            </button>
            <button
              className={`stage-btn ${selectedStage === "Advanced" ? "active" : ""}`}
              onClick={() => handleStageChange("Advanced")}
            >
              ADVANCED
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
                        <span className="lesson-number">{lesson.lesson_order}</span>
                      )}
                      <div className="name-desc-container">
                        <span className="lesson-name">
                          {lesson.title} <span className="lesson-name-th">{lesson.title_th}</span>
                        </span>
                        <span className="lesson-desc">
                          {lesson.subtitle} <span className="lesson-desc-th">{lesson.subtitle_th}</span>
                        </span>
                      </div>
                    </div>
                    <div className="lesson-item-right">
                      <img src="/images/CheckCircle.png" alt="Unfilled Checkmark" className="checkmark-img" />
                    </div>
                  </Link>
                ))}
              </div>
              <div className="mark-finished-row">
                <span className="mark-finished-content">
                  <span className="mark-finished-text">MARK LEVEL {selectedLevel} AS FINISHED</span>
                  <img src="/images/CheckCircle.png" alt="Unfilled Checkmark" className="checkmark-img" />
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
