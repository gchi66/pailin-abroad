import React, { useState } from "react";
import "../Styles/DiscussionBoard.css";

export default function NewCommentForm({ onPost, parentId }) {
  const [body, setBody] = useState("");
  const [posting, setPosting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!body.trim()) return;
    setPosting(true);
    await onPost(body, parentId || null);
    setBody("");
    setPosting(false);
  }

  return (
    <form className="new-comment-form" onSubmit={handleSubmit}>
      <textarea
        value={body}
        onChange={e => setBody(e.target.value)}
        placeholder={parentId ? "Write a reply..." : "Write a new comment..."}
        rows={parentId ? 2 : 3}
        required
      />
      <button type="submit" disabled={posting || !body.trim()}>
        {posting ? "Posting..." : parentId ? "Reply" : "Post"}
      </button>
    </form>
  );
}
