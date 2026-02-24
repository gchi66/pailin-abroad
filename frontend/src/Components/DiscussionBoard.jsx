import React, { useState } from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { resolveAvatarUrl } from "../lib/resolveAvatarUrl";
import "../Styles/DiscussionBoard.css";

function formatDateLabel(createdAt) {
  if (!createdAt) return "";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    }).format(new Date(createdAt));
  } catch (_error) {
    return "";
  }
}

function buildLocationLabel(comment) {
  if (!comment) return "";

  const metadata = comment.metadata || {};
  const rawCandidates = [
    comment.location,
    comment.location_text,
    comment.location_city,
    comment.location_state,
    comment.location_country,
    comment.user_location,
    metadata.location,
    metadata.location_text,
    metadata.city && metadata.country
      ? `${metadata.city}, ${metadata.country}`
      : null,
    metadata.city,
    metadata.state,
    metadata.country,
    comment.users?.location,
    comment.users?.location_text,
    comment.users?.city,
    comment.users?.state,
    comment.users?.country,
  ];

  const seen = new Set();
  const parts = [];

  rawCandidates.forEach((entry) => {
    const value = typeof entry === "string" ? entry : entry?.toString?.();
    if (!value) return;
    const trimmed = value.trim();
    if (!trimmed) return;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    parts.push(trimmed);
  });

  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];

  return parts.join(", ");
}

function buildCommentMeta(comment) {
  const details = [];
  const dateLabel = formatDateLabel(comment?.created_at);
  if (dateLabel) details.push(dateLabel);

  const locationLabel = buildLocationLabel(comment);
  if (locationLabel) details.push(locationLabel);

  return details.join(" · ");
}

export default function DiscussionBoard({
  comments = [],
  onNewComment,
  onReply,
  onPin,
  onDelete,
  canPost = false,
  loginPrompt,
  isLoading = false,
}) {
  const { ui: uiLang } = useUiLang();
  const [newComment, setNewComment] = useState("");
  const [posting, setPosting] = useState(false);
  const resolvedLoginPrompt =
    loginPrompt || t("lessonDiscussion.loginPrompt", uiLang);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = newComment.trim();
    if (!trimmed || !onNewComment) return;

    setPosting(true);
    try {
      await onNewComment(trimmed);
      setNewComment("");
    } finally {
      setPosting(false);
    }
  }

  const commentCount = Array.isArray(comments)
    ? countComments(comments)
    : 0;
  const canReply = typeof onReply === "function" && canPost;
  const canDelete = typeof onDelete === "function";

  return (
    <div className="discussion-container">
      <div className="discussion-wrapper">
        <section className="discussion-board">
          <div className="discussion-header">
            <h2 className="discussion-title">
              {t("lessonDiscussion.title", uiLang)}
            </h2>
            {canPost && onNewComment ? (
              <form className="discussion-form" onSubmit={handleSubmit}>
                <textarea
                  value={newComment}
                  onChange={(event) => setNewComment(event.target.value)}
                  placeholder={t("lessonDiscussion.placeholder", uiLang)}
                  rows={4}
                  className="discussion-textarea"
                  required
                />
                <button
                  type="submit"
                  className="discussion-submit-btn"
                  disabled={posting || !newComment.trim()}
                >
                  {posting
                    ? t("lessonDiscussion.submitting", uiLang)
                    : t("lessonDiscussion.submit", uiLang)}
                </button>
              </form>
            ) : (
              <div className="discussion-locked">
                <p>{resolvedLoginPrompt}</p>
              </div>
            )}
          </div>

          <div className="comments-section">
            <h3 className="comments-title">
              {t("lessonDiscussion.comments", uiLang)} ({commentCount})
            </h3>
            {isLoading ? (
              <div className="discussion-loading">
                {t("lessonDiscussion.loading", uiLang)}
              </div>
            ) : commentCount === 0 ? (
              <div className="discussion-empty">
                {t("lessonDiscussion.empty", uiLang)}
              </div>
            ) : (
              <div className="comments-list">
                {comments.map((comment) => (
                  <CommentItem
                    key={comment.id}
                    comment={comment}
                    onReply={onReply}
                    onPin={onPin}
                    onDelete={onDelete}
                    canReply={canReply}
                    canDelete={canDelete}
                    depth={0}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function countComments(list = []) {
  return list.reduce((total, comment) => {
    const replies = Array.isArray(comment?.replies)
      ? countComments(comment.replies)
      : 0;
    return total + 1 + replies;
  }, 0);
}

function CommentItem({ comment, onReply, onPin, onDelete, canReply, canDelete, depth }) {
  const [replyBody, setReplyBody] = useState("");
  const [replying, setReplying] = useState(false);
  const [submittingReply, setSubmittingReply] = useState(false);
  const { ui: uiLang } = useUiLang();

  const isPinned = Boolean(comment?.pinned);

  const userDisplay =
    comment?.users?.username ||
    comment?.users?.email ||
    comment?.user_email ||
    comment?.user_username ||
    "Anonymous";

  const metaDetails = buildCommentMeta(comment);
  const hasReplies = Array.isArray(comment?.replies) && comment.replies.length > 0;

  return (
    <>
      <div
        className={`comment-card${isPinned ? " comment-card--pinned" : ""}`}
        style={{ "--comment-depth": depth }}
      >
        <div className="comment-avatar">
          {comment?.users?.avatar_image ||
          comment?.users?.avatar ||
          comment?.users?.avatar_url ? (
            <img
              src={
                resolveAvatarUrl(
                  comment.users.avatar_image ||
                  comment.users.avatar ||
                  comment.users.avatar_url ||
                  ""
                )
              }
              alt={userDisplay}
              className="comment-avatar-image"
            />
          ) : (
            <span className="comment-avatar-letter">
              {userDisplay.charAt(0).toUpperCase()}
            </span>
          )}
        </div>
        <div className="comment-main">
          <div className="comment-top-row">
            <div className="comment-author-group">
              <span className="comment-author">{userDisplay?.toUpperCase()}</span>
              {metaDetails && (
                <span className="comment-meta">{metaDetails}</span>
              )}
            </div>
            <div className="comment-top-actions">
              {isPinned && (
                <img
                  src="/images/pinned_comment_pin.png"
                  alt={t("lessonDiscussion.pinnedAlt", uiLang)}
                  className="comment-pin-icon"
                />
              )}
              {typeof onPin === "function" && (
                <button
                  type="button"
                  className="comment-pin-toggle"
                  onClick={() => onPin(comment.id, !isPinned)}
                >
                  {isPinned
                    ? t("lessonDiscussion.unpin", uiLang)
                    : t("lessonDiscussion.pin", uiLang)}
                </button>
              )}
              {canDelete && (
                <button
                  type="button"
                  className="comment-delete-toggle"
                  onClick={() => {
                    if (!onDelete) return;
                    const confirmed = window.confirm(
                      t("lessonDiscussion.deleteConfirm", uiLang)
                    );
                    if (confirmed) onDelete(comment.id);
                  }}
                >
                  {t("lessonDiscussion.delete", uiLang)}
                </button>
              )}
            </div>
          </div>

          <div className="comment-body">
            {comment?.body && (
              <p className="comment-message">{comment.body}</p>
            )}
            {comment?.body_th && (
              <p className="comment-message comment-message--secondary">
                {comment.body_th}
              </p>
            )}
          </div>

          {canReply && (
            <div className="comment-footer">
              <button
                type="button"
                className="comment-reply-toggle"
                onClick={() => setReplying((prev) => !prev)}
              >
                {t("lessonDiscussion.reply", uiLang)}
              </button>
            </div>
          )}

          {canReply && replying && (
            <form
              className="comment-reply-form"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!replyBody.trim() || !onReply) return;
                setSubmittingReply(true);
                try {
                  await onReply(comment, replyBody.trim());
                  setReplyBody("");
                  setReplying(false);
                } finally {
                  setSubmittingReply(false);
                }
              }}
            >
              <textarea
                className="comment-reply-textarea"
                rows={3}
                value={replyBody}
                onChange={(event) => setReplyBody(event.target.value)}
                placeholder={t("lessonDiscussion.placeholder", uiLang)}
                required
              />
              <button
                type="submit"
                className="comment-reply-submit"
                disabled={submittingReply || !replyBody.trim()}
              >
                {submittingReply
                  ? t("lessonDiscussion.submitting", uiLang)
                  : t("lessonDiscussion.submit", uiLang)}
              </button>
            </form>
          )}
        </div>
      </div>
      {hasReplies && (
        <div className="comment-children">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              onReply={onReply}
              onPin={onPin}
              onDelete={onDelete}
              canReply={canReply}
              canDelete={canDelete}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </>
  );
}
