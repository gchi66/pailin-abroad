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
  variant = "card", // "card" (legacy) | "sticky"
  focusText = "",
}) {
  const voiceRef = useRef(null);
  const bgRef = useRef(null);

  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [rate, setRate] = useState(1);
  const [isDraggingVolume, setIsDraggingVolume] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const volumeTrackRef = useRef(null);
  const touchDataRef = useRef(null);
  const touchHandledRef = useRef(false);
  const isScrubbingRef = useRef(false);
  const [showRates, setShowRates] = useState(false);
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

  const handleTrackClick = (e) => {
    if (isLocked) return;
    isScrubbingRef.current = false;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    seek(pct);
  };

  const handleTrackDrag = (e) => {
    if (isLocked) return;
    if (e.buttons !== 1) return; // Only drag with left mouse button
    isScrubbingRef.current = true;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seek(pct);
  };

  const handleTrackPointerDown = () => {
    isScrubbingRef.current = true;
  };

  const handleTrackPointerUp = () => {
    isScrubbingRef.current = false;
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

  const handleVolumeChange = (newVolume) => {
    setVolume(newVolume);
    if (hasSplit) {
      if (voiceRef.current) voiceRef.current.volume = newVolume;
      if (bgRef.current) bgRef.current.volume = newVolume;
    } else {
      if (voiceRef.current) voiceRef.current.volume = newVolume;
    }
    // Mute if volume is 0 or extremely low
    if (newVolume <= 0.01) {
      setMuted(true);
      if (hasSplit) {
        if (voiceRef.current) voiceRef.current.muted = true;
        if (bgRef.current) bgRef.current.muted = true;
      } else {
        if (voiceRef.current) voiceRef.current.muted = true;
      }
    } else if (muted) {
      setMuted(false);
      if (hasSplit) {
        if (voiceRef.current) voiceRef.current.muted = false;
        if (bgRef.current) bgRef.current.muted = false;
      } else {
        if (voiceRef.current) voiceRef.current.muted = false;
      }
    }
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

  const updateVolumeFromPosition = (clientY) => {
    const track = volumeTrackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
    const offset = clamp(rect.bottom - clientY, 0, rect.height);
    const newVolume = rect.height ? offset / rect.height : 0;
    handleVolumeChange(parseFloat(newVolume.toFixed(2)));
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

    const onEnded = () => {
      setPlaying(false);
      setCurrent(0);
      voice.currentTime = 0;
      if (hasSplit && bgRef.current) {
        bgRef.current.pause();
        bgRef.current.currentTime = 0;
      }
    };

    voice.addEventListener("timeupdate", onTime);
    voice.addEventListener("loadedmetadata", onMeta);
    voice.addEventListener("ended", onEnded);

    // Apply current rate
    changeRate(rate);

    return () => {
      voice.removeEventListener("timeupdate", onTime);
      voice.removeEventListener("loadedmetadata", onMeta);
      voice.removeEventListener("ended", onEnded);
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

  const extractClientY = (event) => {
    if (event?.clientY != null) return event.clientY;
    if (event?.touches?.length) return event.touches[0].clientY;
    if (event?.changedTouches?.length) return event.changedTouches[0].clientY;
    return null;
  };

  const handleVolumeMouseDown = (event) => {
    event.preventDefault();
    const clientY = extractClientY(event);
    if (clientY !== null) {
      updateVolumeFromPosition(clientY);
      setIsDraggingVolume(true);
    }
  };

  useEffect(() => {
    if (!isDraggingVolume) return;

    const handleMove = (event) => {
      if (event.cancelable) event.preventDefault();
      const clientY = extractClientY(event);
      if (clientY !== null) {
        updateVolumeFromPosition(clientY);
      }
    };

    const handleUp = (event) => {
      const clientY = extractClientY(event);
      if (clientY !== null) {
        updateVolumeFromPosition(clientY);
      }
      setIsDraggingVolume(false);
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("touchmove", handleMove, { passive: false });
    window.addEventListener("mouseup", handleUp);
    window.addEventListener("touchend", handleUp);
    window.addEventListener("touchcancel", handleUp);

    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("touchmove", handleMove);
      window.removeEventListener("mouseup", handleUp);
      window.removeEventListener("touchend", handleUp);
      window.removeEventListener("touchcancel", handleUp);
    };
  }, [isDraggingVolume]);

  const volumeHandleStyle = {
    bottom: `calc(${((muted ? 0 : volume) * 100).toFixed(2)}% - 0.5rem)`
  };

  const pauseAll = () => {
    if (voiceRef.current) {
      voiceRef.current.pause();
    }
    if (bgRef.current) {
      bgRef.current.pause();
    }
    setPlaying(false);
  };

  const isSticky = variant === "sticky";

  useEffect(() => {
    return () => pauseAll();
  }, []);

  const expand = () => setIsCollapsed(false);
  const collapse = () => setIsCollapsed(true);
  const toggleCollapsed = () => setIsCollapsed((prev) => !prev);

  const handleHandleClick = (event) => {
    event.stopPropagation();
    toggleCollapsed();
  };

  const handleHandleKeyDown = (event) => {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      expand();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      collapse();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleCollapsed();
    }
  };

  const SWIPE_DISTANCE_PX = 16;
  const SWIPE_VELOCITY = 0.6;
  const DOMINANCE_RATIO = 1.5;

  const handleTouchStartBar = (event) => {
    if (!isSticky || isScrubbingRef.current) return;
    const t = event.touches?.[0];
    if (!t) return;
    touchHandledRef.current = false;
    touchDataRef.current = { x: t.clientX, y: t.clientY, time: Date.now() };
  };

  const handleTouchMoveBar = (event) => {
    if (!isSticky || !touchDataRef.current || isScrubbingRef.current) return;
    const t = event.touches?.[0];
    if (!t || touchHandledRef.current) return;

    const deltaX = Math.abs(t.clientX - touchDataRef.current.x);
    const deltaY = t.clientY - touchDataRef.current.y;
    const absY = Math.abs(deltaY);
    const dominantVertical = absY > deltaX * DOMINANCE_RATIO;
    const elapsed = Math.max(1, Date.now() - touchDataRef.current.time);
    const velocity = absY / elapsed;

    if (!dominantVertical) return;

    if (absY > SWIPE_DISTANCE_PX || velocity > SWIPE_VELOCITY) {
      if (deltaY > 0 && !isCollapsed) {
        collapse();
        touchHandledRef.current = true;
      } else if (deltaY < 0 && isCollapsed) {
        expand();
        touchHandledRef.current = true;
      }
    }
  };

  const handleTouchEndBar = () => {
    if (!isSticky) return;
    if (!touchHandledRef.current && isCollapsed) {
      expand();
    }
    touchDataRef.current = null;
    isScrubbingRef.current = false;
    touchHandledRef.current = false;
  };

  const handleTouchCancelBar = () => {
    touchDataRef.current = null;
    touchHandledRef.current = false;
    isScrubbingRef.current = false;
  };

  const handleContainerClick = () => {
    if (isCollapsed) expand();
  };

  return (
    <section
      className={`audio-card${isLocked ? ' audio-locked' : ''}${isSticky ? ' audio-card-sticky' : ''}${isCollapsed ? ' is-collapsed' : ''}`}
      onClick={handleContainerClick}
      onTouchStart={handleTouchStartBar}
      onTouchMove={handleTouchMoveBar}
      onTouchEnd={handleTouchEndBar}
      onTouchCancel={handleTouchCancelBar}
    >
      {variant === "card" && (
        <>
          <h3 className="audio-heading">LISTEN TO THE CONVERSATION</h3>
          {/* {description && <p className="audio-desc">{description}</p>} */}
        </>
      )}

      {/* Locked overlay */}
      {isLocked && (
        <div className="audio-locked-overlay">
          <div className="audio-locked-message">
            <img
              src="/images/lock.webp"
              alt="Locked"
              className="audio-locked-icon"
            />
            <p>Audio is locked. Sign Up to listen!</p>
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
      <div className={`bar-row${isSticky ? " bar-row-sticky" : ""}`}>
        {isSticky && (
          <button
            type="button"
            className="audio-handle"
            onClick={handleHandleClick}
            onKeyDown={handleHandleKeyDown}
            aria-expanded={!isCollapsed}
            aria-label={isCollapsed ? "Expand audio controls" : "Collapse audio controls"}
          />
        )}
        <div className={`audio-controls-wrapper${isCollapsed ? " is-collapsed" : ""}`}>
          <div
            className={isSticky ? "audio-controls audio-sticky-controls" : "audio-controls"}
            onClick={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
          >
            <div className="audio-controls-primary">
              <button
                className="icon-btn play-btn"
                onClick={togglePlay}
                aria-label="Play / Pause"
                disabled={isLocked}
              >
                <img
                  src={playing ? "/images/pause-audio-lesson.webp" : "/images/play-audio-lesson.webp"}
                  alt={playing ? "Pause" : "Play"}
                  className="play-pause-icon"
                />
              </button>

              <span className="time-label">{fmt(current)}</span>

              <div
                className="track"
                role="slider"
                aria-valuemin={0}
                aria-valuemax={duration}
                aria-valuenow={current}
                onMouseDown={handleTrackPointerDown}
                onTouchStart={handleTrackPointerDown}
                onMouseUp={handleTrackPointerUp}
                onTouchEnd={handleTrackPointerUp}
                onClick={handleTrackClick}
                onMouseMove={handleTrackDrag}
              >
                <div
                  className="track-fill"
                  style={{ width: duration ? `${(current / duration) * 100}%` : 0 }}
                >
                  <div className="track-handle" />
                </div>
              </div>

              <span className="time-label">{fmt(duration)}</span>
            </div>

            <div className="audio-controls-secondary">
              <button className="icon-btn skip-btn" onClick={() => skip(-10)} title="Replay 10 s">
                <img
                  src="/images/rewind-audio-10-seconds.webp"
                  alt="Rewind 10 seconds"
                  className="skip-icon"
                />
              </button>
              <button className="icon-btn skip-btn" onClick={() => skip(10)} title="Forward 10 s">
                <img
                  src="/images/forward-audio-10-seconds.webp"
                  alt="Forward 10 seconds"
                  className="skip-icon"
                />
              </button>

              <div className="volume-control">
                <button
                  className={`icon-btn volume-btn${muted ? " is-muted" : ""}`}
                  onClick={toggleMute}
                  aria-label="Mute / Un-mute"
                >
                  <img
                    src="/images/adjust-volume-audio-lesson.webp"
                    alt="Volume"
                    className="volume-icon"
                  />
                </button>
                <div className="volume-slider-container">
                  <div
                    className="volume-slider-wrapper"
                    ref={volumeTrackRef}
                    onMouseDown={handleVolumeMouseDown}
                    onTouchStart={handleVolumeMouseDown}
                  >
                    <div
                      className="volume-slider-fill"
                      style={{ height: `${(muted ? 0 : volume) * 100}%` }}
                    />
                    <div className="volume-handle" style={volumeHandleStyle} />
                  </div>
                </div>
              </div>

              <div className="rate-group">
                <button
                  className="rate-btn current-rate"
                  onClick={() => setShowRates(!showRates)}
                  aria-label="Toggle playback rates"
                >
                  {rate}x
                </button>
                {showRates && (
                  <div className="rate-options">
                    {rates.filter(r => r !== rate).map((r) => (
                      <button
                        key={r}
                        className="rate-btn rate-option"
                        onClick={() => {
                          setRate(r);
                          setShowRates(false);
                        }}
                        aria-label={`Set playback rate to ${r}x`}
                      >
                        {r}x
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        <span className="sr-only" aria-live="polite">
          {isCollapsed ? "Audio player collapsed" : "Audio player expanded"}
        </span>
      </div>
    </section>
  );
}
