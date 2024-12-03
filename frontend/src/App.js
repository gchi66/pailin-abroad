import React from "react";
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
import ProfilePage from "./Pages/ProfilePage"; // Import ProfilePage
// import Footer from './Components/Footer'
import ProtectedRoute from "./Components/ProtectedRoute";
import { AuthProvider } from './AuthContext';

function App() {
  return (
    <div className="App">
      {/* Wrap the entire Router with AuthProvider */}
      <AuthProvider>
        <Router>
          <Header />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/lessons" element={<LessonsIndex />} />
            <Route path="/glossary" element={<Glossary />} />
            <Route path="/contact" element={<Contact />} />
            {/* Define standalone routes for login and signup */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignUpPage />} />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </AuthProvider>
    </div>
  );
}

export default App;
