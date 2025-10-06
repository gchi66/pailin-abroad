// AboutMethod.jsx
import React, { useState } from "react";
import "../Styles/AboutMethod.css";

const AboutMethod = () => {
  const [expandedCards, setExpandedCards] = useState({ 0: true });

  const toggleCard = (index) => {
    setExpandedCards(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const cards = [
    {
      header: "What is the Pailin Abroad method?",
      content: (
        <>
          Pailin Abroad is a narrative-driven English learning platform with over 150 lessons, each based on a conversation. Instead of memorizing disconnected grammar rules or vocabulary lists, you'll follow a continuous story that follows Pailin's life in Los Angeles, which gives you an engaging and natural way of learning English in context.
        </>
      )
    },
    {
      header: "Who is Pailin?",
      content: (
        <>
          Pailin is a 21-year-old girl from Bangkok who will study abroad in Los Angeles for a year.
          <br /><br />
          You'll follow her journey as she navigates friendship, love, family, school, work, and life in a new country. As you get to know Pailin and the other characters, you'll feel connected to their stories and be motivated to move through the narrative, all while improving your English along the way.
          <br /><br />
          <strong>Did you know?</strong> You can see what Pailin is up to in LA on Instagram! @pailinabroad ✨
        </>
      ),
      hasImage: true
    },
    {
      header: "What kind of English will I learn?",
      content: (
        <>
          You'll learn natural, conversational English with Pailin Abroad - the English that native speakers actually use.
          <br /><br />
          Many ESL resources teach stiff, formal English that sounds awkward in casual conversation. We skip that textbook formality and focus on the real-life conversations you'll have with friends, family, coworkers, romantic interests, and strangers.
          <br /><br />
          Our goal is to help you use English to show your true personality. The characters in Pailin Abroad get excited, sad, angry, annoyed, confused, and embarrassed - just like all of us! Through their real-life dialogues, you'll learn authentic ways to express your feelings in English.
        </>
      )
    },
    {
      header: "What English level is Pailin Abroad for?",
      content: (
        <>
          Pailin Abroad is designed to support all levels of English learners! We offer Beginner, Intermediate, and Advanced skill levels, with an Expert level coming soon.
          <br /><br />
          Level 1 of our Beginner course is perfect if you're starting your English learning from scratch.
          <br /><br />
          Best of all, you're not stuck on a pathway - you can jump into any level that suits your skills. But we think that intermediate and advanced learners will still find our beginner lessons interesting and insightful!
        </>
      )
    },
    {
      header: "How does Pailin Abroad specifically benefit Thai people?",
      content: (
        <>
          There are two huge advantages that Pailin Abroad offers for Thai people:
          <br /><br />
          <strong>All content is translated in English and Thai</strong>
          <br />
          Most ESL resources are only available in English, so they're not beginner-friendly! Or, you must use Google Translate for all the content, which leads to wildly inaccurate translations. With Pailin Abroad, you don't have to worry about this - you can just focus on learning.
          <br /><br />
          <strong>All lessons are created by native English speakers who lived in Thailand for years</strong>
          <br />
          Our team understands the unique challenges that Thai people face when learning English. Our Common Mistakes library gives specific insights into the mistakes that Thai people often make, and why. We also offer ways to fix these mistakes!
        </>
      )
    },
    {
      header: "How will Pailin Abroad help me improve my English in the real world?",
      content: (
        <>
          <strong>Has this ever happened to you?</strong>
          <br />
          You study English and feel confident in your skills, but then a native speaker talks so quickly and uses so much slang! You freeze, and suddenly all the English you learned has disappeared.
          <br /><br />
          We totally get it! That's what happens when you learn English out of context, usually from outdated textbooks in the classroom.
          <br /><br />
          In real life, you can't always ask people to slow down or repeat themselves. But with Pailin Abroad, you are in control. You can slow down the audio, replay the conversation, and listen as many times as you need until you fully grasp the dialogue. Soon enough, you'll stop translating every single word into Thai in your head, and you'll start naturally understanding English at a real-life pace.
        </>
      )
    },
    {
      header: "What's included in each lesson?",
      content: (
        <>
          Each lesson contains all or most of these items, in this specific flow to guide your practice:
          <br /><br />
          <strong>Audio Conversation</strong>
          <br />
          Slow down and relisten to the conversation as many times as you need! Try not to look at the translation first - see how much you can understand just by listening.
          <br /><br />
          <strong>Lesson Focus</strong>
          <br />
          Each lesson revolves around one grammar point or key concept that's used throughout the conversation, so you can hear it in a natural context.
          <br /><br />
          <strong>Comprehension Questions</strong>
          <br />
          Test your overall understanding of the conversation.
          <br /><br />
          <strong>Apply</strong>
          <br />
          This is your chance to try using the lesson focus in a sentence on your own before learning about it! This will help concepts stick better in your brain.
          <br /><br />
          <strong>Understand</strong>
          <br />
          Dive into the lesson focus, using the conversation for context. Listen to example sentences with audio to further practice your listening and comprehension skills.
          <br /><br />
          <strong>Extra Tips</strong>
          <br />
          These are tips that can further your understanding of the lesson focus.
          <br /><br />
          <strong>Common Mistakes</strong>
          <br />
          These are common mistakes made by Thai people, along with ways to fix them.
          <br /><br />
          <strong>Phrases & Phrasal Verbs</strong>
          <br />
          We've highlighted the important phrases and phrasal verbs used in the conversation, complete with examples of them used in a sentence.
          <br /><br />
          <strong>Culture Notes</strong>
          <br />
          These are insights into American culture that are mentioned in the conversation that you will find interesting or useful to know.
          <br /><br />
          <strong>Practice</strong>
          <br />
          Every lesson has practice exercises for you to complete to further your understanding of the lesson focus.
          <br /><br />
          <strong>Comment</strong>
          <br />
          Practice your writing skills by responding to the Pinned Comment! We'll respond with personalized feedback and corrections.
        </>
      )
    },
    {
      header: "Who is Pailin Abroad best for?",
      content: (
        <>
          You've definitely heard this advice for learning a language: 'Just go out there and start speaking!'
          <br /><br />
          But the truth is, not all of us are naturally gifted at learning a language just by immersion alone.
          <br /><br />
          Pailin Abroad is designed to be a comfortable, structured space to practice your English and build your confidence. By greatly improving your listening skills with our lessons, you'll no longer feel intimidated to talk with native English speakers!
        </>
      )
    }
  ];

  return (
    <div className="about-method-cards-container">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`about-method-card ${expandedCards[index] ? 'expanded' : ''}`}
          onClick={() => toggleCard(index)}
        >
          <div className={`about-method-card-header-container ${expandedCards[index] ? 'expanded' : ''}`}>
            <span className="about-method-card-header">
              {card.header}
            </span>
            <svg
              className={`about-method-card-arrow ${expandedCards[index] ? 'expanded' : ''}`}
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#1E1E1E"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {expandedCards[index] && (
            <>
              <hr className="about-method-card-line" />

              <div className="about-method-card-content">
                {card.hasImage && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}

                <span className="about-method-card-text">
                  {card.content}
                </span>

                {card.hasImage && card.align === 'right' && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
};

// Ensure this is the only default export in the file
export default AboutMethod;
