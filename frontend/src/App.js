import React, { useState } from "react";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import './Styles/App.css';
import Header from './Components/Header';
import Home from "./Pages/Home";
import LoginPage from "./Pages/LoginPage";
import SignUpPage from "./Pages/SignUpPage";
import AboutPage from "./Pages/AboutPage";
import LessonsIndex from "./Pages/LessonsIndex";
import Glossary from "./Pages/Glossary";
import Contact from "./Pages/Contact";
import Modal from "./Components/Modal";
import ProfilePage from "./Pages/ProfilePage";
import Footer from './Components/Footer'
import ProtectedRoute from "./Components/ProtectedRoute";
import RestrictedRoute from "./Components/RestrictedRoute";
import { AuthProvider } from './AuthContext';

function App() {
  const [modalContent, setModalContent] = useState({ isOpen: false, title: "", message: "" });

  const openModal = (title, message) => {
    setModalContent({ isOpen: true, title, message });
  };

  const closeModal = () => {
    setModalContent({ isOpen: false, title: "", message: "" });
  };

  return (
    <AuthProvider>
      <Router>
        <Header />
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
          <Route path="/glossary" element={<Glossary />} />
          <Route path="/contact" element={<Contact />} />
          {/* Restrict login and signup if already logged in */}
          <Route
            path="/login"
            element={
              <RestrictedRoute openModal={openModal}>
                <LoginPage />
              </RestrictedRoute>
            }
          />
          <Route
            path="/signup"
            element={
              <RestrictedRoute openModal={openModal}>
                <SignUpPage />
              </RestrictedRoute>
            }
          />

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
