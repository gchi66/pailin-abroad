import React, { useState } from "react";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import "./Styles/App.css";
import Navbar from "./Components/Navbar";
import Home from "./Pages/Home";
import AboutPage from "./Pages/AboutPage";
import LessonsIndex from "./Pages/LessonsIndex";
import FreeLessonsIndex from "./Pages/FreeLessonsIndex";
import TryLessons from "./Pages/TryLessons";
import Lesson from "./Pages/Lesson";
import Resources from "./Pages/Resources";
import TopicLibrary from "./Pages/TopicLibrary";
import TopicDetail from "./Pages/TopicDetail";
import Contact from "./Pages/Contact";
import FAQPage from "./Pages/FAQPage";
import Modal from "./Components/Modal";
import AccountSettings from "./Pages/AccountSettings";
import Membership from "./Pages/Membership";
import MyPathway from "./Pages/MyPathway";
import EmailConfirmationPage from "./Pages/EmailConfirmationPage";
import Onboarding from "./Pages/Onboarding";
import Footer from "./Components/Footer";
import ProtectedRoute from "./Components/ProtectedRoute";
import LoginModal from "./Components/LoginModal";
import SignUpModal from "./Components/SignUpModal";
import { AuthProvider } from "./AuthContext";

// ⬇️ import the provider
import { UiLangProvider } from "./ui-lang/UiLangContext";

function App() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isSignupModalOpen, setSignupModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState({ isOpen: false, title: "", message: "" });

  const openModal = (title, message) => setModalContent({ isOpen: true, title, message });
  const closeModal = () => setModalContent({ isOpen: false, title: "", message: "" });
  const toggleLoginModal = () => setIsLoginModalOpen((prev) => !prev);
  const toggleSignupModal = () => setSignupModalOpen((prev) => !prev);

  return (
    <AuthProvider>
      <Router>
        {/* ⬇️ UiLangProvider must be inside the Router */}
        <UiLangProvider>
          <Routes>
            {/* Full-screen onboarding route - isolated from main app structure */}
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/email-confirmation" element={<EmailConfirmationPage />} />
            <Route path="/reset-password" element={<div style={{ padding: '2rem', textAlign: 'center' }}>
              <h2>Password Reset</h2>
              <p>This page will handle password reset functionality.</p>
              <p>You'll be able to set a new password here after clicking the reset link in your email.</p>
            </div>} />

            {/* Main app routes with navbar and footer */}
            <Route path="/*" element={
              <>
                <Navbar
                  toggleLoginModal={toggleLoginModal}
                  toggleSignupModal={toggleSignupModal}
                />
                <LoginModal isOpen={isLoginModalOpen} onClose={toggleLoginModal} toggleSignupModal={toggleSignupModal} />
                <SignUpModal isOpen={isSignupModalOpen} onClose={toggleSignupModal} toggleLoginModal={toggleLoginModal} />
                <Modal
                  isOpen={modalContent.isOpen}
                  title={modalContent.title}
                  message={modalContent.message}
                  onClose={closeModal}
                />
                <Routes>
                  <Route path="/" element={<Home toggleSignupModal={toggleSignupModal} />} />
                  <Route path="/about" element={<AboutPage />} />
                  <Route path="/lessons" element={<LessonsIndex />} />
                  <Route path="/free-lessons" element={<FreeLessonsIndex />} />
                  <Route path="/try-lessons" element={<TryLessons />} />
                  <Route path="/lesson/:id" element={<Lesson />} />
                  <Route path="/pathway" element={<MyPathway />} />
                  <Route path="/resources" element={<Resources />} />
                  <Route path="/topic-library" element={<TopicLibrary />} />
                  <Route path="/topic-library/:slug" element={<TopicDetail />} />
                  <Route path="/contact" element={<Contact />} />
                  <Route path="/faq" element={<FAQPage />} />
                  <Route path="/membership" element={<Membership />} />
                  <Route
                    path="/profile"
                    element={
                      <ProtectedRoute openModal={openModal}>
                        <AccountSettings />
                      </ProtectedRoute>
                    }
                  />
                </Routes>
                <Footer />
              </>
            } />
          </Routes>
        </UiLangProvider>
      </Router>
    </AuthProvider>
  );
}

export default App;
