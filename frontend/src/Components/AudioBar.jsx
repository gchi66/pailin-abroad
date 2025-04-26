import React, { useRef, useState, useEffect } from "react";
import "../Styles/AudioBar.css";

/**
 * Props
 * ─────
 * audioSrc      – full path to the MP3 (local, CDN, or Supabase signed URL)
 * description   – short sentence under the heading (falls back to "")
 * tipsOnClick   – optional handler when the user clicks “LISTENING TIPS”
 */
export default function AudioBar({
  audioSrc = "/audio/sample.mp3",
  description = "",
  // tipsOnClick = () => alert("TODO: open tips modal"),
}) {
  const audio = useRef(null);

  /* ─── state ─────────────────────────────────────────────── */
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [rate, setRate] = useState(1);

  /* ─── event handlers ────────────────────────────────────── */
  const togglePlay = () => {
    if (!audio.current) return;
    playing ? audio.current.pause() : audio.current.play();
    setPlaying(!playing);
  };

  const seek = (pct) => {
    if (!audio.current) return;
    const newTime = duration * pct;
    audio.current.currentTime = newTime;
    setCurrent(newTime);
  };

  const skip = (sec) => {
    if (!audio.current) return;
    audio.current.currentTime = Math.max(
      0,
      Math.min(duration, audio.current.currentTime + sec)
    );
  };

  const toggleMute = () => {
    if (!audio.current) return;
    audio.current.muted = !muted;
    setMuted(!muted);
  };

  const cycleRate = () => {
    const newRate = rate >= 2 ? 1 : +(rate + 0.25).toFixed(2);
    if (audio.current) audio.current.playbackRate = newRate;
    setRate(newRate);
  };

  /* ─── attach listeners once ─────────────────────────────── */
  useEffect(() => {
    const el = audio.current;
    if (!el) return;
    const onTime = () => setCurrent(el.currentTime);
    const onMeta = () => setDuration(el.duration || 0);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("loadedmetadata", onMeta);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("loadedmetadata", onMeta);
    };
  }, []);

  const fmt = (s) =>
    !s ? "0:00" : `${Math.floor(s / 60)}:${`${Math.floor(s % 60)}`.padStart(2, "0")}`;

  return (
    <section className="audio-card">
      <h3 className="audio-heading">LISTEN TO THE CONVERSATION</h3>
      {description && <p className="audio-desc">{description}</p>}

      <audio ref={audio} src={audioSrc} preload="metadata" />

      {/* control row */}
      <div className="bar-row">
        <button className="icon-btn play-btn" onClick={togglePlay} aria-label="Play / Pause">
          {playing ? "⏸" : "▶️"}
        </button>

        <span className="time-label">{fmt(current)}</span>

        {/* progress track */}
        <div
          className="track"
          role="slider"
          aria-valuemin={0}
          aria-valuemax={duration}
          aria-valuenow={current}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            seek(pct);
          }}
        >
          <div
            className="track-fill"
            style={{ width: duration ? `${(current / duration) * 100}%` : 0 }}
          />
        </div>

        <span className="time-label">{fmt(duration)}</span>

        <button className="icon-btn" onClick={() => skip(-10)} title="Replay 10 s">
          ↺10
        </button>
        <button className="icon-btn" onClick={() => skip(10)} title="Forward 10 s">
          ↻10
        </button>

        <button className="icon-btn" onClick={toggleMute} aria-label="Mute / Un-mute">
          {muted ? "🔇" : "🔊"}
        </button>

        <button className="rate-btn" onClick={cycleRate}>
          {rate}x
        </button>
      </div>
{/*
      listening tips
      <button className="tips-row" onClick={tipsOnClick}>
        <span className="tips-icon">💡</span>
        <span className="tips-text">LISTENING TIPS</span>
      </button> */}

    </section>
  );
}
