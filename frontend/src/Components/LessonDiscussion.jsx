import React, { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import DiscussionBoard from "./DiscussionBoard";
import "../Styles/DiscussionBoard.css";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";

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
  const [adminStatus, setAdminStatus] = useState(false);
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  useEffect(() => {
    const fetchAdminStatus = async () => {
      if (!user) {
        setAdminStatus(false);
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("users")
          .select("is_admin")
          .eq("id", user.id)
          .single();

        if (error) {
          console.error("Error fetching admin status:", error.message);
          setAdminStatus(false);
          return;
        }

        setAdminStatus(Boolean(data?.is_admin));
      } catch (error) {
        console.error("Error fetching admin status:", error);
        setAdminStatus(false);
      }
    };

    fetchAdminStatus();
  }, [user]);

  // Fetch comments for this lesson
  useEffect(() => {
    async function fetchComments() {
      setLoading(true);
      const { data, error } = await supabaseClient
        .from("comments")
        .select("*, users(username, email, avatar_image)")
        .eq("lesson_id", lessonId)
        .order("pinned", { ascending: false })
        .order("created_at", { ascending: true });
      if (error) {
        console.error("Error fetching comments:", error.message);
        setLoading(false);
        return;
      }
      setComments(data || []);
      setLoading(false);
    }
    fetchComments();
  }, [lessonId]);

  // Add new comment (requires login)
  async function handleNewComment(body) {
    if (!user) return;
    const { data, error } = await supabaseClient
      .from("comments")
      .insert({ lesson_id: lessonId, user_id: user.id, body })
      .select("*, users(username, email, avatar_image)");
    if (error) {
      console.error("Error creating comment:", error.message);
      return;
    }
    if (data) {
      setComments((prev) => [...prev, ...data]);
      const isAdminUser = Boolean(isAdmin) || adminStatus;
      if (!isAdminUser && data[0]?.id) {
        notifyComment(data[0].id);
      }
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
      .insert({
        lesson_id: lessonId,
        user_id: user.id,
        body: replyBody,
        parent_comment_id: parentComment.id,
      })
      .select("*, users(username, email, avatar_image)");
    if (error) {
      console.error("Error creating reply:", error.message);
      return;
    }
    if (data) {
      setComments(prev => [...prev, ...data]);
    }
  }

  async function handleDelete(commentId) {
    await supabaseClient
      .from("comments")
      .delete()
      .eq("id", commentId);
    setComments((prev) => removeCommentAndReplies(prev, commentId));
  }

  async function notifyComment(commentId) {
    try {
      const {
        data: { session },
      } = await supabaseClient.auth.getSession();
      const token = session?.access_token;
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/api/notify-comment`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ comment_id: commentId }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        console.error("Error notifying comment:", payload?.error || response.status);
      }
    } catch (error) {
      console.error("Error notifying comment:", error);
    }
  }

  // Nest comments for rendering
  const nested = nestComments(comments);
  const canPost = Boolean(user);
  const canAdminReply = Boolean(isAdmin) || adminStatus;

  return (
    <section className="lesson-discussion">
      <DiscussionBoard
        comments={nested}
        onNewComment={canPost ? handleNewComment : undefined}
        onReply={canAdminReply ? handleReply : undefined}
        onPin={canAdminReply ? handlePin : undefined}
        onDelete={canAdminReply ? handleDelete : undefined}
        canPost={canPost}
        loginPrompt={t("lessonDiscussion.loginPrompt", uiLang)}
        isLoading={loading}
      />
    </section>
  );
}

function removeCommentAndReplies(comments, targetId) {
  if (!Array.isArray(comments) || !targetId) return comments;

  const toRemove = new Set([targetId]);
  let added = true;

  while (added) {
    added = false;
    comments.forEach((comment) => {
      if (comment.parent_comment_id && toRemove.has(comment.parent_comment_id)) {
        if (!toRemove.has(comment.id)) {
          toRemove.add(comment.id);
          added = true;
        }
      }
    });
  }

  return comments.filter((comment) => !toRemove.has(comment.id));
}
