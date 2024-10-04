// frontend/src/Home.js

import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Home = () => {
  const [message, setMessage] = useState("");

  useEffect(() => {
    axios.get("http://127.0.0.1:5000/")
      .then((response) => {
        setMessage(response.data.message);
      })
      .catch((error) => {
        console.error("Error fetching data from the backend:", error);
      });
  }, []);

  return (
    <div>
      <h1>Pailin Abroad</h1>
      <p>{message}</p>
    </div>
  );
};

export default Home;
