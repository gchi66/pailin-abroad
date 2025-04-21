import { useParams } from "react-router-dom";
import React, { useState, useEffect } from "react";
import "../Styles/Lesson.css";
import LessonHeader from "../Components/LessonHeader";
import supabaseClient from "../supabaseClient";

export default function Lesson() {
  const { id } = useParams();
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLesson = async () => {
      try {
        const { data, error } = await supabaseClient
          .from('lessons')
          .select('*')
          .eq('id', id)
          .single();

        if (error) throw error;
        setLesson(data);
      } catch (error) {
        console.error('Error fetching lesson:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchLesson();
  }, [id]);

  if (loading) return <div>Loading...</div>;
  if (!lesson) return <div>Lesson not found</div>;

  return (
    <main>
      <div className="lesson-page-container">
        <LessonHeader 
          level={lesson.level}
          lessonOrder={lesson.lesson_order}
          title={lesson.title}
          subtitle={lesson.subtitle}
          titleTh={lesson.title_th}
          subtitleTh={lesson.subtitle_th}
        />
        {/* …rest of the lesson body goes here… */}
      </div>
    </main>
  );
}
