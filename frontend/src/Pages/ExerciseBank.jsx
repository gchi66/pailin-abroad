import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Breadcrumbs from "../Components/Breadcrumbs";
import PlanNotice from "../Components/PlanNotice";
import { useAuth } from "../AuthContext";
import { fetchExerciseBankTopics } from "../lib/exerciseBankV2Api";
import { useUiLang } from "../ui-lang/UiLangContext";
import "../Styles/ExerciseBank.css";

const labels = {
  en: { title: "Exercise Bank", subtitle: "Build your English one topic at a time.", featured: "Featured", all: "All topics", search: "Search topics", loading: "Loading topics…", empty: "No topics found.", sets: "sets complete", questions: "questions", start: "Start practice", continue: "Continue practice", review: "Review topic", newContent: "new content", signInTitle: "Sign in to practise and save your progress", signInBody: "Your answers and completed sets will be saved to your account.", signUp: "Create an account" },
  th: { title: "คลังแบบฝึกหัด", subtitle: "พัฒนาภาษาอังกฤษทีละหัวข้อ", featured: "แนะนำ", all: "ทุกหัวข้อ", search: "ค้นหาหัวข้อ", loading: "กำลังโหลดหัวข้อ…", empty: "ไม่พบหัวข้อ", sets: "ชุดที่สำเร็จ", questions: "คำถาม", start: "เริ่มฝึก", continue: "ฝึกต่อ", review: "ทบทวนหัวข้อ", newContent: "เนื้อหาใหม่", signInTitle: "เข้าสู่ระบบเพื่อฝึกและบันทึกความคืบหน้า", signInBody: "คำตอบและชุดที่ทำสำเร็จจะถูกบันทึกไว้ในบัญชีของคุณ", signUp: "สร้างบัญชี" },
};

const categoryName = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function ExerciseBank() {
  const { user } = useAuth();
  const { ui } = useUiLang();
  const copy = labels[ui] || labels.en;
  const navigate = useNavigate();
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(Boolean(user));
  const [error, setError] = useState("");
  const [view, setView] = useState("featured");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!user) { setLoading(false); setTopics([]); return undefined; }
    const controller = new AbortController();
    setLoading(true); setError("");
    fetchExerciseBankTopics({ signal: controller.signal })
      .then((payload) => setTopics(payload.topics || []))
      .catch((fetchError) => { if (fetchError.name !== "AbortError") setError(fetchError.message); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user]);

  const visibleTopics = useMemo(() => {
    const term = search.trim().toLowerCase();
    return topics.filter((topic) => {
      if (view === "featured" && !topic.is_featured) return false;
      if (!term) return true;
      return [topic.display_title, topic.topic, topic.category, topic.sub_category].filter(Boolean).join(" ").toLowerCase().includes(term);
    });
  }, [search, topics, view]);

  const openTopic = (topicId) => navigate(`/exercise-bank/topics/${topicId}`);

  return <div className="exercise-bank-page-container">
    <header className="exercise-bank-page-header"><div className="exercise-bank-header-content"><h1 className="exercise-bank-page-header-text">{copy.title}</h1><p className="exercise-bank-page-subtitle">{copy.subtitle}</p></div></header>
    <div className="exercise-bank-content">
      <Breadcrumbs className="exercise-bank-breadcrumbs" items={[{ label: "Resources", to: "/resources" }, { label: copy.title }]} />
      {!user && <PlanNotice heading={copy.signInTitle} subtext={copy.signInBody} cta={{ to: "/signup", label: copy.signUp }} />}
      {user && <div className="exercise-bank-toolbar-wrapper"><div className="exercise-bank-toolbar">
        <div className="exercise-bank-toolbar-left exercise-bank-toggle-buttons">
          <button type="button" className={`section-btn ${view === "featured" ? "active" : ""}`} onClick={() => setView("featured")}>{copy.featured}</button>
          <button type="button" className={`section-btn ${view === "all" ? "active" : ""}`} onClick={() => setView("all")}>{copy.all}</button>
        </div>
        <div className="exercise-bank-toolbar-right"><div className="exercise-bank-search"><label className="sr-only" htmlFor="exercise-topic-search">{copy.search}</label><input id="exercise-topic-search" type="search" placeholder={copy.search} value={search} onChange={(event) => setSearch(event.target.value)} /></div></div>
      </div></div>}

      {loading && <div className="exercise-bank-placeholder"><p>{copy.loading}</p></div>}
      {error && <div className="exercise-bank-placeholder"><p>{error}</p></div>}
      {!loading && user && !error && visibleTopics.length === 0 && <div className="exercise-bank-placeholder"><p>{copy.empty}</p></div>}
      {!loading && user && !error && visibleTopics.length > 0 && <div className="exercise-bank-card-grid">{visibleTopics.map((topic) => {
        const progress = topic.progress || {};
        const action = progress.is_current_version_completed ? copy.review : progress.mastered_questions ? copy.continue : copy.start;
        return <article key={topic.id} className="exercise-bank-card exercise-bank-card-clickable" role="link" tabIndex="0" onClick={() => openTopic(topic.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") openTopic(topic.id); }}>
          <div className="exercise-bank-card-header"><div className="exercise-bank-card-section"><h3>{topic.display_title}</h3><p className="exercise-bank-topic-technical-title">{topic.topic}</p></div><div className="exercise-bank-card-meta"><span className="exercise-bank-category-chip">{categoryName(topic.category)}</span>{topic.progress?.has_new_content && <span className="exercise-bank-new-badge">{copy.newContent}</span>}</div></div>
          <div className="exercise-bank-card-body"><div className="exercise-bank-topic-progress-copy"><span>{progress.completed_sets || 0}/{progress.total_sets || 0} {copy.sets}</span><span>{progress.total_questions || 0} {copy.questions}</span></div><div className="exercise-bank-topic-progress"><span style={{ width: `${progress.total_sets ? ((progress.completed_sets || 0) / progress.total_sets) * 100 : 0}%` }} /></div><span className="exercise-bank-card-link">{action}</span></div>
        </article>;
      })}</div>}
      {!user && <div className="exercise-bank-signed-out-action"><Link to="/signup">{copy.signUp}</Link></div>}
    </div>
  </div>;
}
