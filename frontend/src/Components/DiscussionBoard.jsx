
import React, { useState } from "react";
import NewCommentForm from "./NewCommentForm";
import "../Styles/DiscussionBoard.css";

export default function DiscussionBoard({ comments, onReply, onPin }) {
  // comments are already nested and sorted
  return (
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
  );
}

function CommentItem({ comment, onReply, onPin, depth = 0 }) {
  const [showReply, setShowReply] = useState(false);
  const isPinned = !!comment.pinned;
  // Show user info: email or username, and profile picture placeholder
  const userDisplay = comment.user_email || comment.user_username || "Anonymous";
  return (
    <div className={`comment-item${isPinned ? " pinned" : ""}`} style={{ marginLeft: `calc(${depth} * 1.5rem)` }}>
      <div className="comment-header">
        <div className="comment-profile">
          <div className="profile-pic" />
          <span className="profile-name">{userDisplay}</span>
        </div>
        <div className="comment-main">
          <div className="body">{comment.body}</div>
          <div className="comment-actions">
            <button className="reply-btn" onClick={() => setShowReply(v => !v)}>
              {showReply ? "Cancel" : "Reply"}
            </button>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {isPinned && <span className="badge">Pinned</span>}
          <span className="comment-date">{comment.created_at?.slice(0, 10)}</span>
          {onPin && (
            <button className="pin-btn" onClick={() => onPin(comment.id, !isPinned)}>
              {isPinned ? "Unpin" : "Pin"}
            </button>
          )}
        </div>
      </div>
      {showReply && (
        <NewCommentForm onPost={(body) => { onReply?.(comment); setShowReply(false); }} parentId={comment.id} />
      )}
      {/* Render replies recursively */}
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
