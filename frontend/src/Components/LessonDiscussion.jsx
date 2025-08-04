import React, { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import DiscussionBoard from "./DiscussionBoard";
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
  const [newComment, setNewComment] = useState("");
  const [posting, setPosting] = useState(false);
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
  async function handleReply(parentComment, replyBody) {
    if (!user) return;
    const { data, error } = await supabaseClient
      .from("comments")
      .insert({ lesson_id: lessonId, user_id: user.id, body: replyBody, parent_comment_id: parentComment.id })
      .select();
    if (data) {
      setComments(prev => [...prev, ...data]);
    }
  }

  // Nest comments for rendering
  const nested = nestComments(comments);

  async function handleNewCommentSubmit(e) {
    e.preventDefault();
    if (!newComment.trim()) return;
    setPosting(true);
    await handleNewComment(newComment);
    setNewComment("");
    setPosting(false);
  }

  return (
    <section className="lesson-discussion">
      <h3 className="discussion-title">Discussion Board</h3>
      {user ? (
        <form className="new-comment-form" onSubmit={handleNewCommentSubmit}>
          <textarea
            value={newComment}
            onChange={e => setNewComment(e.target.value)}
            placeholder="Write a new comment..."
            rows={3}
            className="comment-textarea"
            required
          />
          <button type="submit" className="comment-submit-btn" disabled={posting || !newComment.trim()}>
            {posting ? "Posting..." : "Post"}
          </button>
        </form>
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
