import React, { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import DiscussionBoard from "./DiscussionBoard";
import NewCommentForm from "./NewCommentForm";
import "../Styles/DiscussionBoard.css";
import { useAuth } from "../AuthContext";

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

  // Fetch comments for this lesson
  useEffect(() => {
    async function fetchComments() {
      setLoading(true);
      const { data, error } = await supabaseClient
        .from("comments")
        .select("*")
        .eq("lesson_id", lessonId)
        .order("pinned", { ascending: false })
        .order("created_at", { ascending: true });
      setComments(data || []);
      setLoading(false);
    }
    fetchComments();
  }, [lessonId]);

  // Add new comment (requires login)
  async function handleNewComment(body, parentCommentId = null) {
    if (!user) return;
    const { data, error } = await supabaseClient
      .from("comments")
      .insert({ lesson_id: lessonId, user_id: user.id, body, parent_comment_id: parentCommentId })
      .select();
    if (error) {
      console.error("Insert failed:", error.message, error.details);
    }
    if (data) {
      setComments(prev => [...prev, ...data]);
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
  function handleReply(parentComment) {
    // Could open a reply form inline, handled in CommentItem
  }

  // Nest comments for rendering
  const nested = nestComments(comments);

  return (
    <section className="lesson-discussion">
      <h3 className="discussion-title">Discussion Board</h3>
      {user ? (
        <NewCommentForm onPost={handleNewComment} />
      ) : (
        <div className="discussion-login-msg">You must be logged in to post a comment.</div>
      )}
      {loading ? (
        <div className="discussion-loading">Loading comments…</div>
      ) : (
        <DiscussionBoard
          comments={nested}
          onReply={handleReply}
          onPin={isAdmin ? handlePin : undefined}
        />
      )}
    </section>
  );
}
