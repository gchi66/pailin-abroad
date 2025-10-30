import { useState } from "react";
import supabaseClient from "../supabaseClient";
import "../Styles/AudioBullet.css";

// Use public URL for image instead of import
const playPng = "/images/snippet_play_button.png";

/**
 * Universal AudioButton component for all sections
 *
 * This component handles audio playback across all lesson content with a smart fallback system:
 * 1. First tries to find audio by audio_key (e.g., "1.15_understand_01", "1.7_practice_02")
 * 2. Falls back to phrases audio lookup (phrase_id + variant + seq)
 * 3. Finally falls back to legacy audio_section + audio_seq lookup
 *
 * Usage:
 * - For nodes with audio_key: Just pass audioKey and audioIndex
 * - For phrases: Pass phraseId, phraseVariant, phrasesSnipIdx, and node with audio_seq
 * - For legacy audio: Pass node with audio_section/audio_seq and audioIndex
 *
 * @param {string} audioKey - The audio key to look up (e.g., "1.15_practice_01")
 * @param {Object} node - The node containing audio_seq/audio_section for fallback
 * @param {Object} audioIndex - The audio index containing by_key lookup and section/seq lookup
 * @param {Object} phrasesSnipIdx - The phrases audio index for phrases sections
 * @param {string} phraseId - The phrase ID for phrases sections
 * @param {number} phraseVariant - The phrase variant for phrases sections
 * @param {number} size - Size in rem units (default: 1.2)
 * @param {string} className - Additional CSS classes
 */
export default function AudioButton({
  audioKey,
  node,
  audioIndex,
  phrasesSnipIdx,
  phraseId,
  phraseVariant = 0,
  size = 1.2, // rem
  className = ""
}) {
  const [url, setUrl] = useState();

  // Try audio_key first (preferred method) - now includes both standard and phrases audio
  let snip = null;
  let lookupMethod = "none";

  // Check both the audioKey prop and node.audio_key field
  const effectiveAudioKey = audioKey || node?.audio_key;

  if (effectiveAudioKey && audioIndex?.by_key?.[effectiveAudioKey]) {
    snip = audioIndex.by_key[effectiveAudioKey];
    lookupMethod = "audio_key";
  }
  // Fallback to phrases audio if in phrases section (legacy)
  else if (phraseId && phrasesSnipIdx?.idx?.[phraseId]?.[phraseVariant]?.[node?.audio_seq]) {
    snip = phrasesSnipIdx.idx[phraseId][phraseVariant][node.audio_seq];
    lookupMethod = "phrases_legacy";
  }
  // Fallback to section/seq lookup (legacy)
  else if (node?.audio_section && node?.audio_seq && audioIndex?.[node.audio_section]?.[node.audio_seq]) {
    snip = audioIndex[node.audio_section][node.audio_seq];
    lookupMethod = "audio_seq_legacy";
  }

  // Don't render anything if no snippet found
  if (!snip) return null;

  async function play() {
    console.log("🎵 Universal Audio button clicked!");
    console.log("lookupMethod:", lookupMethod);
    console.log("audioKey prop:", audioKey, "node.audio_key:", node?.audio_key, "effectiveAudioKey:", effectiveAudioKey);
    console.log("phraseId:", phraseId, "node.audio_section:", node?.audio_section, "node.audio_seq:", node?.audio_seq);
    console.log("snip found:", snip);

    if (!snip) {
      console.error("❌ No snip found for audioKey:", audioKey);
      return;
    }

    console.log("snip.storage_path:", snip.storage_path);

    if (!url) {
      console.log("🔄 No cached URL, fetching signed URL...");

      try {
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

        console.log("✅ Successfully got signed URL:", data.signedUrl);
        setUrl(data.signedUrl);

        const audio = new Audio(data.signedUrl);
        audio.addEventListener('error', (e) => console.error("❌ Audio error:", e));

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
      const audio = new Audio(url);
      audio.addEventListener('error', (e) => console.error("❌ Audio error (cached):", e));

      try {
        await audio.play();
        console.log("✅ Audio.play() completed successfully (cached)");
      } catch (playError) {
        console.error("❌ Audio.play() failed (cached):", playError);
      }
    }
  }

  const hasSnip = !!snip;
  const buttonStyle = {
    width: `${size}rem`,
    height: `${size}rem`,
    // marginRight: `${size * 0.42}rem`,
    cursor: hasSnip ? 'pointer' : 'not-allowed',
    opacity: hasSnip ? 1 : 0.3,
    flexShrink: 0
  };

  return (
    <img
      src={playPng}
      onClick={play}
      className={`audio-button select-none ${className}`.trim()}
      style={buttonStyle}
      alt="Play audio"
      title={hasSnip ? "Click to play audio" : "No audio snippet found"}
    />
  );
}
