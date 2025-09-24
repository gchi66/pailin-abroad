import React, { useState } from "react";
import "../Styles/DiscussionBoard.css";

export default function DiscussionBoard({ comments = [], onReply, onPin }) {
  // Inline new comment form state
  const [newComment, setNewComment] = useState("");
  const [posting, setPosting] = useState(false);

  async function handleNewCommentSubmit(e) {
    e.preventDefault();
    if (!newComment.trim()) return;
    setPosting(true);
    await onReply?.(null, newComment);
    setNewComment("");
    setPosting(false);
  }

  return (
    <div className="discussion-container">
      <div className="discussion-wrapper">
        <section className="discussion-board">
          {comments.map((c) => (
            <CommentItem
              key={c.id}
              comment={c}
              onReply={onReply}
              onPin={onPin}
            />
          ))}
        </section>
      </div>
    </div>
  );
}

function CommentItem({ comment, onReply, onPin, depth = 0 }) {
  const [showReply, setShowReply] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const [postingReply, setPostingReply] = useState(false);
  const isPinned = !!comment.pinned;

  // Get username from the joined users table
  const userDisplay = comment.users?.username ||
                     comment.users?.email ||
                     comment.user_email ||
                     comment.user_username ||
                     "Anonymous";

  async function handleReplySubmit(e) {
    e.preventDefault();
    if (!replyBody.trim()) return;
    setPostingReply(true);
    await onReply?.(comment, replyBody);
    setReplyBody("");
    setPostingReply(false);
    setShowReply(false);
  }

  return (
    <div
      className={`comment-item ${isPinned ? 'pinned' : ''}`}
      style={{ marginLeft: `${depth * 24}px` }}
    >
      <div className="comment-layout">
        <div className="profile-section">
          <div className="profile-pic">
            {comment.users?.avatar_image ? (
              <img
                src={comment.users.avatar_image}
                alt={userDisplay}
                className="profile-pic-image"
              />
            ) : (
              <span className="profile-pic-letter">
                {userDisplay.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
        </div>
        <div className="content-section">
          <div className="comment-header">
            <span className="username">{userDisplay}</span>
            <span className="timestamp">
              {new Date(comment.created_at).toLocaleDateString()}
            </span>
            {isPinned && (
              <span className="pinned-badge">
                📌 Pinned
              </span>
            )}
            {onPin && (
              <button
                className="pin-btn"
                onClick={() => onPin(comment.id, !isPinned)}
              >
                {isPinned ? "Unpin" : "Pin"}
              </button>
            )}
          </div>
          <div className="comment-body">
            {comment.body}
            {comment.body_th && (
              <div className="comment-th">{comment.body_th}</div>
            )}
          </div>
          <div className="comment-actions">
            <button
              className="reply-btn"
              onClick={() => setShowReply(v => !v)}
            >
              {showReply ? "Cancel" : "Reply"}
            </button>
          </div>
          {showReply && (
            <form className="new-comment-form reply-form-container" onSubmit={handleReplySubmit}>
              <textarea
                value={replyBody}
                onChange={e => setReplyBody(e.target.value)}
                placeholder="Write a reply..."
                rows={2}
                className="comment-textarea"
                required
              />
              <button type="submit" className="submit-btn" disabled={postingReply || !replyBody.trim()}>
                {postingReply ? "Posting..." : "Reply"}
              </button>
            </form>
          )}
        </div>
      </div>
      {comment.replies && comment.replies.length > 0 && (
        <div className="comment-replies">
          {comment.replies.map(reply => (
            <CommentItem
              key={reply.id}
              comment={reply}
              onReply={onReply}
              onPin={onPin}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
