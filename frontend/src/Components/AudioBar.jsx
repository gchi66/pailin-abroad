import React, { useRef, useState, useEffect } from "react";
import "../Styles/AudioBar.css";

/**
 * Props
 * ─────
 * audioSrc        – full mix file (voices + bg)
 * audioSrcNoBg    – voices only (optional)
 * audioSrcBg      – background only (optional)
 * description     – optional description
 * isLocked        – whether the lesson is locked (disables playback)
 */
export default function AudioBar({
  audioSrc,
  audioSrcNoBg,
  audioSrcBg,
  description = "",
  isLocked = false,
}) {
  const voiceRef = useRef(null);
  const bgRef = useRef(null);

  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [rate, setRate] = useState(1);
  const rates = [0.5, 0.75, 1, 1.25, 1.5];

  // Decide mode: split or fallback
  const hasSplit = !!(audioSrcNoBg && audioSrcBg);

  const togglePlay = () => {
    if (isLocked) return; // Disable playback for locked lessons

    if (hasSplit) {
      if (!voiceRef.current || !bgRef.current) return;
      if (playing) {
        voiceRef.current.pause();
        bgRef.current.pause();
      } else {
        // sync before starting
        bgRef.current.currentTime = voiceRef.current.currentTime;
        voiceRef.current.play();
        bgRef.current.play();
      }
    } else {
      if (!voiceRef.current) return;
      playing ? voiceRef.current.pause() : voiceRef.current.play();
    }
    setPlaying(!playing);
  };

  const seek = (pct) => {
    if (isLocked) return; // Disable seeking for locked lessons

    if (!voiceRef.current) return;
    const newTime = duration * pct;
    voiceRef.current.currentTime = newTime;
    if (hasSplit && bgRef.current) {
      bgRef.current.currentTime = newTime;
    }
    setCurrent(newTime);
  };

  const skip = (sec) => {
    if (isLocked) return; // Disable skipping for locked lessons

    if (!voiceRef.current) return;
    const newTime = Math.max(
      0,
      Math.min(duration, voiceRef.current.currentTime + sec)
    );
    voiceRef.current.currentTime = newTime;
    if (hasSplit && bgRef.current) {
      bgRef.current.currentTime = newTime;
    }
  };

  const toggleMute = () => {
    if (hasSplit) {
      if (voiceRef.current) voiceRef.current.muted = !muted;
      if (bgRef.current) bgRef.current.muted = !muted;
    } else {
      if (voiceRef.current) voiceRef.current.muted = !muted;
    }
    setMuted(!muted);
  };

  // Handle rate change
  const changeRate = (newRate) => {
    setRate(newRate);

    if (hasSplit) {
      // Only change voice playback rate
      if (voiceRef.current) {
        voiceRef.current.playbackRate = newRate;
      }
      // Background stays at 1x speed for quality preservation
      if (bgRef.current) {
        bgRef.current.playbackRate = 1;
      }
    } else {
      // Single file mode - change rate normally
      if (voiceRef.current) {
        voiceRef.current.playbackRate = newRate;
      }
    }
  };

  // Attach listeners
  useEffect(() => {
    const voice = voiceRef.current;
    if (!voice) return;

    let lastSyncTime = 0;
    const SYNC_INTERVAL = 500; // Only sync every 500ms
    const SYNC_THRESHOLD = 0.25; // Larger threshold for less frequent syncing

    const onTime = () => {
      setCurrent(voice.currentTime);

      // Dynamic time mapping for background sync with throttling
      if (hasSplit && bgRef.current) {
        const now = Date.now();
        const targetBgTime = voice.currentTime;
        const timeDiff = Math.abs(bgRef.current.currentTime - targetBgTime);

        // Only sync if:
        // 1. Enough time has passed since last sync AND there's drift
        // 2. OR there's significant drift (> 1 second) - emergency sync
        const shouldSync =
          (now - lastSyncTime > SYNC_INTERVAL && timeDiff > SYNC_THRESHOLD) ||
          timeDiff > 1.0;

        if (shouldSync) {
          bgRef.current.currentTime = targetBgTime;
          lastSyncTime = now;
        }
      }
    };

    const onMeta = () => setDuration(voice.duration || 0);

    voice.addEventListener("timeupdate", onTime);
    voice.addEventListener("loadedmetadata", onMeta);

    // Apply current rate
    changeRate(rate);

    return () => {
      voice.removeEventListener("timeupdate", onTime);
      voice.removeEventListener("loadedmetadata", onMeta);
    };
  }, [rate, hasSplit]);

  // Handle rate changes when rate state updates
  useEffect(() => {
    changeRate(rate);
  }, [rate, hasSplit]);

  const fmt = (s) =>
    !s
      ? "0:00"
      : `${Math.floor(s / 60)}:${`${Math.floor(s % 60)}`.padStart(2, "0")}`;

  return (
    <section className={`audio-card${isLocked ? ' audio-locked' : ''}`}>
      <h3 className="audio-heading">LISTEN TO THE CONVERSATION</h3>
      {description && <p className="audio-desc">{description}</p>}

      {/* Locked overlay */}
      {isLocked && (
        <div className="audio-locked-overlay">
          <div className="audio-locked-message">
            <img
              src="/images/lock.webp"
              alt="Locked"
              className="audio-locked-icon"
            />
            <p>Audio is locked. Sign up to listen!</p>
          </div>
        </div>
      )}

      {/* audio elements */}
      {hasSplit ? (
        <>
          <audio ref={voiceRef} src={audioSrcNoBg} preload="metadata" />
          <audio ref={bgRef} src={audioSrcBg} preload="auto" />
        </>
      ) : (
        <audio ref={voiceRef} src={audioSrc} preload="metadata" />
      )}

      {/* controls */}
      <div className="bar-row">
        <button
          className="icon-btn play-btn"
          onClick={togglePlay}
          aria-label="Play / Pause"
          disabled={isLocked}
        >
          {playing ? "⏸" : "▶️"}
        </button>

        <span className="time-label">{fmt(current)}</span>

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

        <button className="icon-btn" onClick={() => skip(-10)} title="Replay 10 s">
          ↺10
        </button>
        <button className="icon-btn" onClick={() => skip(10)} title="Forward 10 s">
          ↻10
        </button>

        <button className="icon-btn" onClick={toggleMute} aria-label="Mute / Un-mute">
          {muted ? "🔇" : "🔊"}
        </button>

        <div className="rate-group">
          {rates.map((r) => (
            <button
              key={r}
              className={`rate-btn${rate === r ? " active" : ""}`}
              onClick={() => setRate(r)}
              aria-label={`Set playback rate to ${r}x`}
            >
              {r}x
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
