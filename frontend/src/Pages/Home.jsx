import React, { useEffect, useState } from "react";
import axios from "axios";
import Landing from "../Components/Landing";
import About from "../Components/About";
import Characters from "../Components/Characters";
import Reviews from "../Components/Reviews";

const Home = () => {
  const [message, setMessage] = useState(""); // State to store the backend message

  const handleChatClick = () => {
    alert("Chat feature coming soon!");
  };

  useEffect(() => {
    axios
      .get("http://127.0.0.1:5000/")
      .then((response) => {
        setMessage(response.data.message);
      })
      .catch((error) => {
        console.error("Error fetching data from the backend:", error);
      });
  }, []);

  return (
    <div>
      <Landing />
      <About />
      <Characters />
      <Reviews />
      <button className="chat-button" onClick={handleChatClick}>
        Let's Chat!
      </button>
      {message && <p className="backend-message">{message}</p>}
    </div>
  );
};

export default Home;
