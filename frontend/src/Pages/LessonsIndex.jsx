import React, { useState }  from "react";
import "../Styles/LessonsIndex.css";


const LessonsIndex = () => {
  const [isBackstoryOpen, setIsBackstoryOpen] = useState(false);
  const lessons = [
    {
      id: 1,
      title: "Hi, I'm Pailin",
      title_th: "สวัสดี ฉันชื่อไพลิน",
      subtitle: "Learn how to greet someone",
      subtitle_th: "เรียนรู้วิธีทักทายใครสักคน"
    },
    {
      id: 2,
      title: "It's nice to meet you",
      title_th: "ยินดีที่ได้รู้จัก",
      subtitle: "What to say when meeting someone for the first time",
      subtitle_th: "จะพูดอะไรเมื่อเจอใครครั้งแรก"
    },
    {
      id: 3,
      title: "How are you?",
      title_th: "คุณเป็นอย่างไร",
      subtitle: "How to ask how someone is doing",
      subtitle_th: "วิธีที่จะถามว่าใครบางคนเป็นอย่างไรบ้าง"
    },
    {
      id: 4,
      title: "Good morning, Joey!",
      title_th: "สวัสดีตอนเช้า, โจอี้!",
      subtitle: "How to greet someone in the morning",
      subtitle_th: "วิธีทักทายใครสักคนในตอนเช้า"
    },
    {
      id: 5,
      title: "What's your name?",
      title_th: "คุณชื่ออะไร",
      subtitle: "How to ask someone's name politely",
      subtitle_th: "วิธีถามชื่อของใครบางคนอย่างสุภาพ"
    },
    {
      id: 6,
      title: "I'm excited!",
      title_th: "ฉันตื่นเต้น!",
      subtitle: "How to express excitement",
      subtitle_th: "วิธีแสดงความตื่นเต้น"
    },
    {
      id: 7,
      title: "How old are you?",
      title_th: "คุณอายุเท่าไหร่",
      subtitle: "How to ask someone’s age",
      subtitle_th: "วิธีถามอายุของใครบางคน"
    },
    {
      id: 8,
      title: "Thanks, I made it!",
      title_th: "ขอบคุณ ฉันทำเอง!",
      subtitle: "How to respond to compliments",
      subtitle_th: "วิธีตอบรับคำชม"
    },
    {
      id: 9,
      title: "You're a good cook",
      title_th: "คุณทำอาหารเก่ง",
      subtitle: "How to compliment someone's cooking",
      subtitle_th: "วิธีชมฝีมือทำอาหารของใครบางคน"
    },
    {
      id: 10,
      title: "Chiang Mai is a beautiful city",
      title_th: "เชียงใหม่เป็นเมืองที่สวยงาม",
      subtitle: "How to describe a place",
      subtitle_th: "วิธีบรรยายสถานที่"
    },
    {
      id: 11,
      title: "Where are you from?",
      title_th: "คุณมาจากที่ไหน",
      subtitle: "How to ask about someone's hometown",
      subtitle_th: "วิธีถามเกี่ยวกับบ้านเกิดของใครบางคน"
    },
    {
      id: 12,
      title: "Do you like Thai food?",
      title_th: "คุณชอบอาหารไทยไหม",
      subtitle: "How to ask about food preferences",
      subtitle_th: "วิธีถามเกี่ยวกับความชอบอาหาร"
    },
    {
      id: 13,
      title: "This is my family",
      title_th: "นี่คือครอบครัวของฉัน",
      subtitle: "How to introduce family members",
      subtitle_th: "วิธีแนะนำสมาชิกในครอบครัว"
    },
    {
      id: 14,
      title: "What do you do?",
      title_th: "คุณทำงานอะไร",
      subtitle: "How to ask about someone's job",
      subtitle_th: "วิธีถามเกี่ยวกับอาชีพของใครบางคน"
    },
    {
      id: 15,
      title: "I love traveling!",
      title_th: "ฉันรักการเดินทาง!",
      subtitle: "How to talk about travel experiences",
      subtitle_th: "วิธีพูดเกี่ยวกับประสบการณ์การเดินทาง"
    },
    {
      id: 16,
      title: "Level 1 Checkpoint",
      title_th: "ฉันรักการเดินทาง!",
      subtitle: "How to greet someone in the morning",
      subtitle_th: "วิธีพูดเกี่ยวกับประสบการณ์การเดินทาง"
    }
  ];

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-header-text">LESSON LIBRARY</h1>
        <img src="/images/books-lesson-library.webp" alt="Library Books" className="header-image" />
      </header>
      <div className="lesson-library">
        {/* The level buttons and placement test header */}
        <div className="level-btns-and-subtitle">
          <p className="lesson-subtitle">
            Not sure where to start? Take our <a href="#">Free Placement Test</a>.
          </p>

          <div className="lesson-levels">
            <button className="level-btn">BEGINNER</button>
            <button className="level-btn">LOWER INTERMEDIATE</button>
            <button className="level-btn">UPPER INTERMEDIATE</button>
            <button className="level-btn">ADVANCED</button>
          </div>

          <div className="lesson-btns">
            <button className="tab-btn">LEVEL 1</button>
            <button className="tab-btn">LEVEL 2</button>
            <button className="tab-btn">LEVEL 3</button>
            <button className="tab-btn">LEVEL 4</button>
          </div>

        </div>

        <div className="level-wrapper">
          <div className="level-container">
            <section className="level-backstory">
            <div className={`level-header ${isBackstoryOpen ? "backstory-open" : ""}`} onClick={() => setIsBackstoryOpen(!isBackstoryOpen)}>
                <div className="level-text-graphic">
                  <span className="level-header-text">LEVEL 1</span>
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
                {lessons.map((lesson, index) => (
                  <div key={lesson.id} className="lesson-item">
                    <div className="lesson-item-left">
                      {index === lessons.length - 1 ? (
                        <img src="/images/black-checkmark-level-checkpoint.webp" alt="Lesson Checkpoint" className="level-checkmark" />
                      ) : (
                        <span className="lesson-number">{index + 1}</span>
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
                  </div>
                ))}
              </div> {/* lesson-list */}
              <div className="mark-finished-row">
                <span className="mark-finished-content">
                  <span className="mark-finished-text">MARK LEVEL 1 AS FINISHED</span>
                  <img src="/images/CheckCircle.png" alt="Unfilled Checkmark" className="checkmark-img" />
                </span>
              </div>
            </div> {/* level-content */}

          </div>
        </div>
      </div>
    </div>
  );
};

export default LessonsIndex;
