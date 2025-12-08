import React from "react";
import "../Styles/LessonContent.css";

export default function PinnedComment({ comment }) {
  return (
    <section className="lc-card" style={{ margin: "2rem auto 0 auto", maxWidth: 800 }}>
      <div className="lc-head">
        <div className="lc-head-left pinned-comment-head">
          <img
            src="/images/pinned_comment_pin.png"
            alt="Pinned comment pin"
            className="lc-pin-icon"
          />
          <span className="lc-head-title">Pinned Comment</span>
        </div>
      </div>
      <div className="lc-body" style={{ minHeight: "6rem" }}>
        {comment && comment.trim() !== "" ? (
          <div style={{ whiteSpace: "pre-line" }}>{comment}</div>
        ) : (
          <div style={{ color: "#6b7280" }}>
            No pinned comment yet. Be the first to post your thoughts about this lesson!
          </div>
        )}
      </div>
    </section>
  );
}
