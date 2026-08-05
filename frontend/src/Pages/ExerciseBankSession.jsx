import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Breadcrumbs from "../Components/Breadcrumbs";
import {
  fetchExerciseBankSet,
  fetchExerciseBankTopic,
  submitExerciseBankAnswer,
} from "../lib/exerciseBankV2Api";
import { useUiLang } from "../ui-lang/UiLangContext";
import "../Styles/ExerciseBankSession.css";

const text = {
  en: {
    bank: "Exercise Bank", set: "Set", question: "Question", of: "of",
    submit: "Check answer", submitting: "Checking…", continue: "Continue",
    retry: "Retry missed questions", topics: "Back to topics", correct: "Correct!",
    incorrect: "Not quite yet", complete: "Set finished", choose: "Choose a set",
    empty: "There are no questions in this set.", reload: "Try again",
    placeholder: "Type your answer", rewrite: "Rewrite the sentence",
    originalCorrect: "The sentence is correct", originalIncorrect: "The sentence is incorrect",
    mastered: "mastered", reviewed: "You reviewed all questions in this set.",
  },
  th: {
    bank: "คลังแบบฝึกหัด", set: "ชุดที่", question: "คำถาม", of: "จาก",
    submit: "ตรวจคำตอบ", submitting: "กำลังตรวจ…", continue: "ต่อไป",
    retry: "ลองคำถามที่พลาดอีกครั้ง", topics: "กลับไปที่หัวข้อ", correct: "ถูกต้อง!",
    incorrect: "ยังไม่ถูกต้อง", complete: "จบชุดแบบฝึกหัด", choose: "เลือกชุดแบบฝึกหัด",
    empty: "ไม่มีคำถามในชุดนี้", reload: "ลองอีกครั้ง", placeholder: "พิมพ์คำตอบ",
    rewrite: "เขียนประโยคใหม่", originalCorrect: "ประโยคนี้ถูกต้อง",
    originalIncorrect: "ประโยคนี้ไม่ถูกต้อง", mastered: "ทำสำเร็จ", reviewed: "คุณทบทวนคำถามทั้งหมดในชุดนี้แล้ว",
  },
};

function ErrorState({ message, onRetry }) {
  return <main className="exercise-session-state"><h1>Exercise Bank</h1><p>{message}</p><button onClick={onRetry}>Try again</button><Link to="/exercise-bank">Back to topics</Link></main>;
}

function BasicQuestion({ question, value, onChange, disabled, labels }) {
  const type = question.exercise?.exercise_type;
  const content = question.content || {};
  const stem = content.stem || content.text || "";
  const isJudgment = type === "sentence_transform" && /correct.*incorrect|incorrect.*correct/i.test(question.exercise?.display_type || "");

  if (type === "multiple_choice") {
    return <div className="exercise-session-options">{(content.options || []).map((option) => (
      <button key={option.label} type="button" disabled={disabled} className={value === option.label ? "is-selected" : ""} onClick={() => onChange(option.label)}>
        <span>{option.label}</span>{option.text}
      </button>
    ))}</div>;
  }

  if (isJudgment) {
    const judgment = value?.marked_as_correct;
    return <div className="exercise-session-judgment">
      <div className="exercise-session-options exercise-session-options-inline">
        <button type="button" disabled={disabled} className={judgment === true ? "is-selected" : ""} onClick={() => onChange({ marked_as_correct: true, rewrite: "" })}>{labels.originalCorrect}</button>
        <button type="button" disabled={disabled} className={judgment === false ? "is-selected" : ""} onClick={() => onChange({ marked_as_correct: false, rewrite: value?.rewrite || "" })}>{labels.originalIncorrect}</button>
      </div>
      {judgment === false && <textarea disabled={disabled} value={value?.rewrite || ""} onChange={(event) => onChange({ marked_as_correct: false, rewrite: event.target.value })} placeholder={labels.rewrite} />}
    </div>;
  }

  const multiline = type === "sentence_transform" || type === "open" || type === "open_ended";
  if (multiline) return <textarea disabled={disabled} value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder={labels.placeholder} />;
  return <input type="text" disabled={disabled} value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder={labels.placeholder} aria-label={stem || labels.placeholder} />;
}

const hasAnswer = (answer) => {
  if (typeof answer === "string") return answer.trim().length > 0;
  if (answer && typeof answer === "object") {
    if (typeof answer.marked_as_correct !== "boolean") return false;
    return answer.marked_as_correct || Boolean(answer.rewrite?.trim());
  }
  return false;
};

export default function ExerciseBankSession() {
  const { topicId, setNumber } = useParams();
  const navigate = useNavigate();
  const { ui } = useUiLang();
  const labels = text[ui] || text.en;
  const [topic, setTopic] = useState(null);
  const [setData, setSetData] = useState(null);
  const [queue, setQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [finished, setFinished] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(""); setFinished(false); setResults({}); setAnswers({});
    try {
      if (!setNumber) {
        const payload = await fetchExerciseBankTopic(topicId);
        const loadedTopic = payload.topic;
        setTopic(loadedTopic);
        if (loadedTopic.next_incomplete_set) {
          navigate(`/exercise-bank/topics/${topicId}/sets/${loadedTopic.next_incomplete_set}`, { replace: true });
        }
        return;
      }
      const payload = await fetchExerciseBankSet(topicId, setNumber);
      setTopic(payload.topic); setSetData(payload.set);
      const incomplete = payload.set.questions.filter((question) => !question.progress?.has_answered_correctly);
      setQueue((incomplete.length ? incomplete : payload.set.questions).map((question) => question.id));
      setQueueIndex(0);
    } catch (loadError) { setError(loadError.message); }
    finally { setLoading(false); }
  }, [navigate, setNumber, topicId]);

  useEffect(() => { load(); }, [load]);

  const questionsById = useMemo(() => new Map((setData?.questions || []).map((question) => [question.id, question])), [setData]);
  const currentQuestion = questionsById.get(queue[queueIndex]);
  const currentResult = currentQuestion ? results[currentQuestion.id] : null;

  const submit = async () => {
    if (!currentQuestion || !hasAnswer(answers[currentQuestion.id])) return;
    setSubmitting(true); setError("");
    try {
      const result = await submitExerciseBankAnswer(currentQuestion.id, answers[currentQuestion.id]);
      setResults((previous) => ({ ...previous, [currentQuestion.id]: result }));
      if (result.correct) {
        setSetData((previous) => ({ ...previous, questions: previous.questions.map((question) => question.id === currentQuestion.id ? { ...question, progress: { ...question.progress, has_answered_correctly: true } } : question) }));
      }
    } catch (submitError) { setError(submitError.message); }
    finally { setSubmitting(false); }
  };

  const advance = () => {
    if (queueIndex < queue.length - 1) setQueueIndex((index) => index + 1);
    else setFinished(true);
  };

  const retryMissed = () => {
    const missed = (setData?.questions || []).filter((question) => !question.progress?.has_answered_correctly).map((question) => question.id);
    setQueue(missed); setQueueIndex(0); setFinished(false);
    setResults((previous) => Object.fromEntries(Object.entries(previous).filter(([id]) => !missed.includes(Number(id)))));
    setAnswers((previous) => Object.fromEntries(Object.entries(previous).filter(([id]) => !missed.includes(Number(id)))));
  };

  if (loading) return <main className="exercise-session-state"><div className="exercise-session-spinner" aria-label="Loading" /></main>;
  if (error && !topic && !setData) return <ErrorState message={error} onRetry={load} />;

  if (!setNumber && topic) return <main className="exercise-session-page"><div className="exercise-session-picker"><h1>{topic.display_title}</h1><p>{labels.choose}</p><div>{topic.sets.map((item) => <Link key={item.set_number} to={`/exercise-bank/topics/${topicId}/sets/${item.set_number}`}>{labels.set} {item.set_number}<small>{item.mastered_questions}/{item.question_count} {labels.mastered}</small></Link>)}</div><Link className="exercise-session-text-link" to="/exercise-bank">{labels.topics}</Link></div></main>;
  if (!setData || !currentQuestion) return <ErrorState message={labels.empty} onRetry={load} />;

  const mastered = setData.questions.filter((question) => question.progress?.has_answered_correctly).length;
  if (finished) return <main className="exercise-session-page"><div className="exercise-session-summary"><span className="exercise-session-summary-icon">✓</span><h1>{labels.complete}</h1><p>{mastered === setData.question_count ? labels.reviewed : `${mastered}/${setData.question_count} ${labels.mastered}`}</p>{mastered < setData.question_count && <button onClick={retryMissed}>{labels.retry}</button>}<Link to="/exercise-bank">{labels.topics}</Link></div></main>;

  const feedback = ui === "th" ? currentResult?.feedback_th : currentResult?.feedback_en;
  const position = queueIndex + 1;
  return <main className="exercise-session-page">
    <div className="exercise-session-shell">
      <Breadcrumbs items={[{ label: labels.bank, to: "/exercise-bank" }, { label: topic?.display_title || topic?.topic }, { label: `${labels.set} ${setData.set_number}` }]} />
      <header className="exercise-session-header"><div><span>{labels.set} {setData.set_number}</span><strong>{labels.question} {position} {labels.of} {queue.length}</strong></div><div className="exercise-session-progress" aria-label={`${position} of ${queue.length}`}><span style={{ width: `${(position / queue.length) * 100}%` }} /></div></header>
      <section className="exercise-session-card">
        <div className="exercise-session-type">{currentQuestion.exercise?.display_type}</div>
        <h1>{currentQuestion.exercise?.prompt}</h1>
        {(currentQuestion.content?.stem || currentQuestion.content?.text) && <p className="exercise-session-stem">{currentQuestion.content.stem || currentQuestion.content.text}</p>}
        <BasicQuestion question={currentQuestion} value={answers[currentQuestion.id]} onChange={(value) => setAnswers((previous) => ({ ...previous, [currentQuestion.id]: value }))} disabled={Boolean(currentResult)} labels={labels} />
        {error && <p className="exercise-session-inline-error" role="alert">{error}</p>}
        {currentResult && <div className={`exercise-session-feedback ${currentResult.correct ? "is-correct" : "is-incorrect"}`}><strong>{currentResult.correct ? labels.correct : labels.incorrect}</strong>{feedback && <p>{feedback}</p>}</div>}
        <div className="exercise-session-actions">{currentResult ? <button onClick={advance}>{labels.continue}</button> : <button onClick={submit} disabled={submitting || !hasAnswer(answers[currentQuestion.id])}>{submitting ? labels.submitting : labels.submit}</button>}</div>
      </section>
    </div>
  </main>;
}
