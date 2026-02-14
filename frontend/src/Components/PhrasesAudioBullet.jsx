import { useState } from "react";
import supabaseClient from "../supabaseClient";
import "../Styles/AudioBullet.css";

// Use public URL for image instead of import
const playPng = "/images/snippet_play_button.png";

export default function PhrasesAudioBullet({
  node,
  phrasesSnipIdx,
  renderInlines,
  phraseId,
  variant = 0
}) {
  // For phrases, we need to look up audio by phrase_id, variant, and seq
  const snip = phrasesSnipIdx?.idx?.[phraseId]?.[variant]?.[node.audio_seq];

  const [url, setUrl] = useState();

  async function play() {

    if (!snip) {
      console.error("❌ No phrases snip found - cannot play audio");
      return;
    }


    if (!url) {

      try {
        if (snip?.signed_url) {
          setUrl(snip.signed_url);
          const audio = new Audio(snip.signed_url);
          await audio.play();
          return;
        }

        const { data, error } = await supabaseClient.storage
          .from("lesson-audio")
          .createSignedUrl(snip.storage_path, 60);


        if (error) {
          console.error("❌ Supabase signed URL error:", error);
          return;
        }

        if (!data || !data.signedUrl) {
          console.error("❌ No signed URL returned from Supabase");
          return;
        }

        setUrl(data.signedUrl);

        const audio = new Audio(data.signedUrl);

        // Add audio event listeners for debugging
        audio.addEventListener('error', (e) => console.error("❌ Audio error:", e));

        try {
          await audio.play();
        } catch (playError) {
          console.error("❌ Audio.play() failed:", playError);
        }

      } catch (fetchError) {
        console.error("❌ Error in fetch process:", fetchError);
      }
    } else {

      const audio = new Audio(url);

      // Add audio event listeners for debugging
      audio.addEventListener('error', (e) => console.error("❌ Audio error (cached):", e));

      try {
        await audio.play();
      } catch (playError) {
        console.error("❌ Audio.play() failed (cached):", playError);
      }
    }
  }

  // Visual indicator for debugging - show if snip is found
  const hasSnip = !!snip;
  const buttonStyle = hasSnip ? {} : { opacity: 0.3, cursor: 'not-allowed' };

  return (
    <li
      className="audio-bullet"
    >
      <img
        src={playPng}
        onClick={play}
        className="mt-0.5 h-5 w-5 select-none"
        style={buttonStyle}
        alt="Play snippet"
        title={hasSnip ? "Click to play audio" : "No audio snippet found"}
      />
      <span>{renderInlines(node.inlines)}</span>
      {/* Debug info - remove this later */}
      <small style={{ color: '#666', marginLeft: '8px' }}>
        [seq:{node.audio_seq}] {hasSnip ? '✅' : '❌'}
      </small>
    </li>
  );
}
