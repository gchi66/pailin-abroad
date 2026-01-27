import React, { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import DiscussionBoard from "./DiscussionBoard";
import "../Styles/DiscussionBoard.css";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

// Utility to nest comments by parent_comment_id
function nestComments(comments) {
  const map = {};
  comments.forEach(c => (map[c.id] = { ...c, replies: [] }));
  const roots = [];
  comments.forEach(c => {
    if (c.parent_comment_id && map[c.parent_comment_id]) {
      map[c.parent_comment_id].replies.push(map[c.id]);
    } else {
      roots.push(map[c.id]);
    }
  });
  return roots;
}

export default function LessonDiscussion({ lessonId, isAdmin }) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  // Fetch comments for this lesson
  useEffect(() => {
    async function fetchComments() {
      setLoading(true);
      const { data } = await supabaseClient
        .from("comments")
        .select("*, users(username, email, avatar_image)")
        .eq("lesson_id", lessonId)
        .order("pinned", { ascending: false })
        .order("created_at", { ascending: true });
      setComments(data || []);
      setLoading(false);
    }
    fetchComments();
  }, [lessonId]);

  // Add new comment (requires login)
  async function handleNewComment(body) {
    if (!user) return;
    const { data } = await supabaseClient
      .from("comments")
      .insert({ lesson_id: lessonId, user_id: user.id, body })
      .select();
    if (data) {
      setComments((prev) => [...prev, ...data]);
    }
  }

  // Pin/unpin comment (admin only)
  async function handlePin(commentId, pinned) {
    await supabaseClient
      .from("comments")
      .update({ pinned })
      .eq("id", commentId);
    setComments(prev => prev.map(c => c.id === commentId ? { ...c, pinned } : c));
  }

  // Reply handler
  async function handleReply(parentComment, replyBody) {
    if (!user) return;
    const { data } = await supabaseClient
      .from("comments")
      .insert({ lesson_id: lessonId, user_id: user.id, body: replyBody, parent_comment_id: parentComment.id })
      .select();
    if (data) {
      setComments(prev => [...prev, ...data]);
    }
  }

  // Nest comments for rendering
  const nested = nestComments(comments);
  const canPost = Boolean(user);

  return (
    <section className="lesson-discussion">
      <DiscussionBoard
        comments={nested}
        onNewComment={canPost ? handleNewComment : undefined}
        onReply={canPost ? handleReply : undefined}
        onPin={isAdmin ? handlePin : undefined}
        canPost={canPost}
        loginPrompt={t("lessonDiscussion.loginPrompt", uiLang)}
        isLoading={loading}
      />
    </section>
  );
}
