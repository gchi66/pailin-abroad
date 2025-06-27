import { useState } from "react";
import supabaseClient from "../supabaseClient";

// Use public URL for image instead of import
const playPng = "/images/snippet_play_button.png";

export default function AudioBullet({ node, snipIdx, renderInlines }) {
  const snip = snipIdx?.[node.audio_section]?.[node.audio_seq];
  const [url, setUrl] = useState();

  async function play() {
    if (!snip) return;
    if (!url) {
      const { data, error } = await supabaseClient.storage
        .from("lesson-audio")
        .createSignedUrl(snip.storage_path, 60);
      if (error) return console.error(error);
      setUrl(data.signedUrl);
      new Audio(data.signedUrl).play();
    } else {
      new Audio(url).play();
    }
  }

  return (
    <li className="flex items-start gap-2 pb-1">
      <img
        src={playPng}
        onClick={play}
        className="mt-0.5 h-5 w-5 cursor-pointer select-none"
        alt="Play snippet"
      />
      <span>{renderInlines(node.inlines)}</span>
    </li>
  );
}
