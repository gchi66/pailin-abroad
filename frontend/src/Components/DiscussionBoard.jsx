import React, { useState } from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
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

  const commentCount = Array.isArray(comments) ? comments.length : 0;
  const canReply = typeof onReply === "function" && canPost;

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
                    canReply={canReply}
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

function CommentItem({ comment, onReply, onPin, canReply, depth }) {
  const [replyBody, setReplyBody] = useState("");
  const { ui: uiLang } = useUiLang();

  const isPinned = Boolean(comment?.pinned);

  const userDisplay =
    comment?.users?.username ||
    comment?.users?.email ||
    comment?.user_email ||
    comment?.user_username ||
    "Anonymous";

  const metaDetails = buildCommentMeta(comment);

  return (
    <div
      className={`comment-card${isPinned ? " comment-card--pinned" : ""}`}
      style={{ "--comment-depth": depth }}
    >
      <div className="comment-avatar">
        {comment?.users?.avatar_image ? (
          <img
            src={comment.users.avatar_image}
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

        {/* Reply functionality removed per request */}
      </div>
    </div>
  );
}
