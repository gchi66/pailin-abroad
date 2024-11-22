import React from "react";
import Header from './Components/Header';
import Landing from './Components/Landing';
import About from './Components/About'
import Reviews from "./Components/Reviews";
// import Footer from './Components/Footer'
import './Styles/App.css';
import Characters from "./Components/Characters";

function App() {
  return (
    <div className="App">
      <Header />
      <Landing />
      {/* <Footer /> */}
      <About />
      <Characters />
      <Reviews />
    </div>
  );
}

export default App;
