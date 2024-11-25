import React from "react";
import Header from './Components/Header';
import Home from "./Pages/Home";
// import Landing from './Components/Landing';
// import About from './Components/About'
// import Reviews from "./Components/Reviews";
// import Footer from './Components/Footer'
import './Styles/App.css';
// import Characters from "./Components/Characters";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import LoginPage from "./Pages/LoginPage";
import SignUpPage from "./Pages/SignUpPage";

function App() {
  return (
    <div className="App">
      <Router>
        <Header />
        <Routes>
          {/* Define the main landing page route */}
          <Route
            path="/"
            element={
              <>
                <Home />
                {/* <Footer /> */}
              </>
            }
          />
          {/* Define standalone routes for login and signup */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignUpPage />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App;
