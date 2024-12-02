import React, { useEffect, useState } from "react";
import axios from "axios";
import supabaseClient from "../supabaseClient";
import Landing from "../Components/Landing";
import About from "../Components/About";
import Characters from "../Components/Characters";
import Reviews from "../Components/Reviews";

const Home = () => {
  const [message, setMessage] = useState(""); // State to store the backend message
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const handleChatClick = () => {
    alert("Chat feature coming soon!");
  };

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const { data: { user } } = await supabaseClient.auth.getUser(); // Updated to use getUser
        setIsLoggedIn(!!user);
      } catch (error) {
        console.error("Error fetching user:", error.message);
      }
    };
    fetchUser();
  }, []);

  useEffect(() => {
    axios
      .get("http://127.0.0.1:5000/")
      .then((response) => {
        setMessage(response.data.message);
      })
      .catch((error) => {
        console.error("Error fetching data from the backend:", error.message);
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
