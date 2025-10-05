import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import "../Styles/TopicLibrary.css";

const TopicLibrary = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const response = await fetch('/api/topic-library');
        if (!response.ok) {
          throw new Error('Failed to fetch topics');
        }
        const data = await response.json();
        setTopics(data.topics || []);
      } catch (err) {
        console.error('Error fetching topics:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTopics();
  }, []);

  if (loading) {
    return (
      <div className="topic-library-page-container">
        <header className="topic-library-page-header">
          <div className="topic-library-header-content">
            <h1 className="topic-library-page-header-text">TOPIC LIBRARY</h1>
            <p className="topic-library-page-subtitle">Further explanations on a range of interesting ESL topics</p>
          </div>
        </header>
        <div className="topic-library-content">
          <p>Loading topics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="topic-library-page-container">
        <header className="topic-library-page-header">
          <div className="topic-library-header-content">
            <h1 className="topic-library-page-header-text">TOPIC LIBRARY</h1>
            <p className="topic-library-page-subtitle">Further explanations on a range of interesting ESL topics</p>
          </div>
        </header>
        <div className="topic-library-content">
          <p>Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="topic-library-page-container">
      {/* page header */}
      <header className="topic-library-page-header">
        <div className="topic-library-header-content">
          <h1 className="topic-library-page-header-text">TOPIC LIBRARY</h1>
          <p className="topic-library-page-subtitle">Further explanations on a range of interesting ESL topics</p>
        </div>
      </header>

      {/* Topics List */}
      <div className="topic-library-content">
        <div className="topic-library-list">
          {topics.length === 0 ? (
            <div className="topic-library-placeholder">
              <h3>No topics available yet</h3>
              <p>Topics will appear here when they are added to the library.</p>
            </div>
          ) : (
            topics.map((topic, index) => (
              <Link
                key={topic.id}
                to={`/topic-library/${topic.slug}`}
                className="topic-library-item"
              >
                <div className="topic-library-content-wrapper">
                  <div className="topic-library-header">
                    <div className="topic-library-number">
                      {(index + 1).toString().padStart(2, '0')}
                    </div>
                    <div className="topic-library-text">
                      <h3 className="topic-library-title">{topic.name}</h3>
                      {topic.subtitle && (
                        <p className="topic-library-subtitle">{topic.subtitle}</p>
                      )}
                      {topic.tags && topic.tags.length > 0 && (
                        <div className="topic-library-tags">
                          {topic.tags.map((tag, tagIndex) => (
                            <span key={tagIndex} className="topic-library-tag">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="topic-library-arrow">→</div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default TopicLibrary;
