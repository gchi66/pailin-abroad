import React, { useEffect, useState } from "react";
import axios from "axios";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import Hero from "../Components/Hero";
import FreeLessonCards from "../Components/FreeLessonCards";
import ChooseUs from "../Components/ChooseUs";
import HowItWorks from '../Components/HowItWorks';
import SignUpCTA from '../Components/SignUpCTA';
import TakeTheLeapCTA from '../Components/TakeTheLeapCTA';
import FAQ from '../Components/FAQ';


// import About from "../Components/About";
import Characters from "../Components/Characters";
import Reviews from "../Components/Reviews";

const Home = ({ toggleSignupModal }) => {
  const [message, setMessage] = useState("");

  // const handleChatClick = () => {
  //   alert("Chat feature coming soon!");
  // };

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const { data } = await supabaseClient.auth.getUser(); // Updated to use getUser
      } catch (error) {
        console.error("Error fetching user:", error.message);
      }
    };
    fetchUser();
  }, []);

  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/`)
      .then((response) => {
        setMessage(response.data.message);
      })
      .catch((error) => {
        console.error("Error fetching data from the backend:", error.message);
      });
  }, []);

  return (
    <div>
      <Hero onSignupClick={toggleSignupModal} />
      <FreeLessonCards />
      <SignUpCTA onSignupClick={toggleSignupModal} />
      {/* <ReusablePlacementTest /> */}
      <ChooseUs />
      <HowItWorks />
      <SignUpCTA onSignupClick={toggleSignupModal} />
      <Characters />
      <Reviews />
      <TakeTheLeapCTA onSignupClick={toggleSignupModal} />
      <FAQ />

      {message && <p className="backend-message">{message}</p>}
    </div>
  );
};

export default Home;
