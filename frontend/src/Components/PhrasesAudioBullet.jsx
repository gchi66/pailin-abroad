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
    console.log("🎵 Phrases Audio button clicked!");
    console.log("phraseId:", phraseId);
    console.log("variant:", variant);
    console.log("node.audio_seq:", node.audio_seq);
    console.log("snip found:", snip);

    if (!snip) {
      console.error("❌ No phrases snip found - cannot play audio");
      return;
    }

    console.log("snip.storage_path:", snip.storage_path);

    if (!url) {
      console.log("🔄 No cached URL, fetching signed URL...");

      try {
        const { data, error } = await supabaseClient.storage
          .from("lesson-audio")
          .createSignedUrl(snip.storage_path, 60);

        console.log("Supabase response - data:", data);
        console.log("Supabase response - error:", error);

        if (error) {
          console.error("❌ Supabase signed URL error:", error);
          return;
        }

        if (!data || !data.signedUrl) {
          console.error("❌ No signed URL returned from Supabase");
          return;
        }

        console.log("✅ Successfully got signed URL:", data.signedUrl);
        setUrl(data.signedUrl);

        console.log("🎵 Creating new Audio object and attempting to play...");
        const audio = new Audio(data.signedUrl);

        // Add audio event listeners for debugging
        audio.addEventListener('loadstart', () => console.log("🔄 Audio loading started"));
        audio.addEventListener('canplay', () => console.log("✅ Audio can start playing"));
        audio.addEventListener('play', () => console.log("▶️ Audio play event fired"));
        audio.addEventListener('error', (e) => console.error("❌ Audio error:", e));
        audio.addEventListener('ended', () => console.log("⏹️ Audio playback ended"));

        try {
          await audio.play();
          console.log("✅ Audio.play() completed successfully");
        } catch (playError) {
          console.error("❌ Audio.play() failed:", playError);
        }

      } catch (fetchError) {
        console.error("❌ Error in fetch process:", fetchError);
      }
    } else {
      console.log("🔄 Using cached URL:", url);
      console.log("🎵 Creating new Audio object with cached URL...");

      const audio = new Audio(url);

      // Add audio event listeners for debugging
      audio.addEventListener('loadstart', () => console.log("🔄 Audio loading started (cached)"));
      audio.addEventListener('canplay', () => console.log("✅ Audio can start playing (cached)"));
      audio.addEventListener('play', () => console.log("▶️ Audio play event fired (cached)"));
      audio.addEventListener('error', (e) => console.error("❌ Audio error (cached):", e));
      audio.addEventListener('ended', () => console.log("⏹️ Audio playback ended (cached)"));

      try {
        await audio.play();
        console.log("✅ Audio.play() completed successfully (cached)");
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
