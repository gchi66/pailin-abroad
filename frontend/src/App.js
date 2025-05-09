import React, { useState } from "react";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import './Styles/App.css';
import Navbar from './Components/Navbar';
import Home from "./Pages/Home";
import AboutPage from "./Pages/AboutPage";
import LessonsIndex from "./Pages/LessonsIndex";
import Lesson from "./Pages/Lesson";
import Resources from "./Pages/Resources";
import Contact from "./Pages/Contact";
import Modal from "./Components/Modal";
import ProfilePage from "./Pages/ProfilePage";
import Membership from "./Pages/Membership";
import Footer from './Components/Footer'
import ProtectedRoute from "./Components/ProtectedRoute";
import LoginModal from "./Components/LoginModal";
import SignupModal from "./Components/SignupModal";
import { AuthProvider } from './AuthContext';

function App() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isSignupModalOpen, setSignupModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState({ isOpen: false, title: "", message: "" });

  const openModal = (title, message) => {
    setModalContent({ isOpen: true, title, message });
  };

  const closeModal = () => {
    setModalContent({ isOpen: false, title: "", message: "" });
  };

  const toggleLoginModal = () => {
    setIsLoginModalOpen((prev) => !prev);
  };
  const toggleSignupModal = () => {
    setSignupModalOpen((prev) => !prev);
  };

  return (
    <AuthProvider>
      <Router>
        <Navbar
        toggleLoginModal={toggleLoginModal}
        toggleSignupModal={toggleSignupModal}
        />
        <LoginModal isOpen={isLoginModalOpen} onClose={toggleLoginModal} />
        <SignupModal isOpen={isSignupModalOpen} onClose={toggleSignupModal} />
        <Modal
          isOpen={modalContent.isOpen}
          title={modalContent.title}
          message={modalContent.message}
          onClose={closeModal}
        />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/lessons" element={<LessonsIndex />} />
          <Route path="/lesson/:id" element={<Lesson />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/membership" element={<Membership />} />
          {/* Protect profile page */}
          <Route
            path="/profile"
            element={
              <ProtectedRoute openModal={openModal}>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
        </Routes>
        <Footer />
      </Router>
    </AuthProvider>
  );
}

export default App;
