import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import TopicRichSectionRenderer from "../Components/TopicRichSectionRenderer";
import "../Styles/TopicDetail.css";

const TopicDetail = () => {
  const { slug } = useParams();
  const [topic, setTopic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTopic = async () => {
      try {
        const response = await fetch(`/api/topic-library/${slug}`);
        if (!response.ok) {
          throw new Error('Topic not found');
        }
        const data = await response.json();
        setTopic(data.topic);
      } catch (err) {
        console.error('Error fetching topic:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (slug) {
      fetchTopic();
    }
  }, [slug]);

  if (loading) {
    return (
      <div className="topic-detail-page-container">
        <div className="topic-detail-header">
          <h1 className="topic-detail-header-text">Loading...</h1>
        </div>
        <div className="topic-detail-content">
          <p>Loading topic content...</p>
        </div>
      </div>
    );
  }

  if (error || !topic) {
    return (
      <div className="topic-detail-page-container">
        <div className="topic-detail-header">
          <h1 className="topic-detail-header-text">Topic Not Found</h1>
        </div>
        <div className="topic-detail-content">
          <p>Error: {error || 'Topic not found'}</p>
          <Link to="/topic-library" className="topic-detail-back-link">
            ← Back to Topic Library
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="topic-detail-page-container">
      {/* Topic header */}
      <header className="topic-detail-header">
        <h1 className="topic-detail-header-text">{topic.name}</h1>
      </header>

      {/* Navigation */}
      <div className="topic-detail-nav">
        <Link to="/topic-library" className="topic-detail-back-link">
          ← Back to Topic Library
        </Link>
        {topic.tags && topic.tags.length > 0 && (
          <div className="topic-detail-tags">
            {topic.tags.map((tag, index) => (
              <span key={index} className="topic-detail-tag">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Topic Content */}
      <div className="topic-detail-content">
        {topic.content_jsonb && topic.content_jsonb.length > 0 ? (
          <TopicRichSectionRenderer 
            nodes={topic.content_jsonb}
            uiLang="en"
          />
        ) : (
          <div className="topic-detail-placeholder">
            <p>No content available for this topic yet.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TopicDetail;