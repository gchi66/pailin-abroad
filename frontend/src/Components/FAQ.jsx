import React, { useState } from "react";
import "../Styles/FAQ.css";

const FAQ = () => {
  const [openCard, setOpenCard] = useState(null);

  const faqData = [
    {
      id: 1,
      question: "How is Pailin Abroad different from other English-learning platforms?",
      answer: "Pailin Abroad focuses on real-world conversational English through engaging storytelling. Unlike traditional platforms that rely on isolated grammar lessons, we follow Pailin's authentic journey in America, giving you context for every phrase and expression. Our content is created by native English speakers and fully translated to Thai, making complex concepts accessible while teaching you the natural flow of American English conversations."
    },
    {
      id: 2,
      question: "Which skills does Pailin Abroad focus on?",
      answer: "We primarily focus on listening comprehension and conversational speaking skills. Through our audio-based lessons, you'll develop your ability to understand natural English conversations, improve your pronunciation, learn common phrases and expressions, and build confidence in real-world communication scenarios. Each lesson also includes cultural insights to help you navigate American social situations."
    },
    {
      id: 3,
      question: "Do you offer a free trial?",
      answer: "Yes! We offer a comprehensive library of free lessons that you can access immediately - no credit card required. Simply sign up with your email to start learning with Pailin right away. Our free content gives you a great taste of our teaching style and the quality of our lessons before you decide on a membership."
    },
    {
      id: 4,
      question: "What are your membership options?",
      answer: "We offer 3 affordable membership options, which you can check out here. For the cost of one private English lesson, you can get a whole month of Pailin Abroad! If you're not ready for membership, you can sign up to access our library of free lessons! Click here to sign up - no credit card needed!"
    }
  ];

  const toggleCard = (cardId) => {
    setOpenCard(openCard === cardId ? null : cardId);
  };

  return (
    <section className="faq-section">
      <h2 className="faq-title">Frequently Asked Questions</h2>
      <div className="faq-cards-container">
        {faqData.map((faq) => (
          <div key={faq.id} className="faq-card">
            <div
              className="faq-header"
              onClick={() => toggleCard(faq.id)}
            >
              <h3 className="faq-question">{faq.question}</h3>
              <span className={`faq-arrow ${openCard === faq.id ? 'open' : ''}`}>
                ▼
              </span>
            </div>
            <div className={`faq-content ${openCard === faq.id ? 'open' : ''}`}>
              <p className="faq-answer">{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default FAQ;
