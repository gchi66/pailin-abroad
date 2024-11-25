import React from "react";

const SearchBar = () => {
  return (
    <div className="search-bar">
      <input type="text" placeholder="" />
      <button className="search-icon">
        <img src="/images/glass.png" alt="Search" />
      </button>
    </div>
  );
};

export default SearchBar;
