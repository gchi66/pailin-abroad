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
  shouldAutoPlay = false,
  onAutoPlayComplete,
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
  const [isDraggingPanel, setIsDraggingPanel] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isSnapping, setIsSnapping] = useState(false);
  const [showVolume, setShowVolume] = useState(false);
  const volumeTrackRef = useRef(null);
  const volumeControlRef = useRef(null);
  const isScrubbingRef = useRef(false);
  const panelDragStartRef = useRef(null);
  const dragOffsetRef = useRef(0);
  const controlsWrapperRef = useRef(null);
  const controlsHeightRef = useRef(0);
  const cardRef = useRef(null);
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

  const forcePlay = () => {
    if (isLocked) return;
    if (hasSplit) {
      if (!voiceRef.current || !bgRef.current) return;
      bgRef.current.currentTime = voiceRef.current.currentTime;
      voiceRef.current.play().catch(() => {});
      bgRef.current.play().catch(() => {});
    } else {
      if (!voiceRef.current) return;
      voiceRef.current.play().catch(() => {});
    }
    setPlaying(true);
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

  const handleTrackTouchMove = (event) => {
    if (isLocked) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    if (event.cancelable) event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
    seek(pct);
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

  const handleVolumeTouchMove = (event) => {
    if (event.cancelable) event.preventDefault();
    const clientY = extractClientY(event);
    if (clientY !== null) {
      updateVolumeFromPosition(clientY);
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
    if (isDraggingPanel) return;
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

  const startPanelDrag = (clientY) => {
    if (!isSticky || isScrubbingRef.current) return;
    panelDragStartRef.current = { y: clientY, time: Date.now() };
    controlsHeightRef.current = controlsWrapperRef.current?.scrollHeight || 0;
    setIsDraggingPanel(true);
  };

  const applyPanelDrag = (clientY) => {
    if (!isSticky || !panelDragStartRef.current || isScrubbingRef.current) return;
    const deltaY = clientY - panelDragStartRef.current.y;
    const maxOffset = controlsHeightRef.current || 200;
    dragOffsetRef.current = deltaY;

    // Visual offset should never move above the natural position (no negative translateY).
    let visualOffset;
    if (isCollapsed) {
      // Only allow downward movement visually; keep at 0 when dragging up.
      visualOffset = Math.max(0, Math.min(maxOffset, deltaY));
    } else {
      // Expanded: allow downward drag up to maxOffset.
      visualOffset = Math.max(0, Math.min(maxOffset, deltaY));
    }

    setDragOffset(visualOffset);
  };

  const finishPanelDrag = () => {
    if (!isSticky || !panelDragStartRef.current) {
      setIsDraggingPanel(false);
      setDragOffset(0);
      dragOffsetRef.current = 0;
      return;
    }

    const deltaY = dragOffsetRef.current;
    const elapsed = Math.max(1, Date.now() - panelDragStartRef.current.time);
    const velocity = Math.abs(deltaY) / elapsed;
    const distThreshold = (controlsHeightRef.current || 150) * 0.4;
    const velThreshold = 0.3;

    let nextCollapsed = isCollapsed;
    if (!isCollapsed && deltaY > 0) {
      if (deltaY > distThreshold || velocity > velThreshold) {
        nextCollapsed = true;
      }
    } else if (isCollapsed && deltaY < 0) {
      if (Math.abs(deltaY) > distThreshold || velocity > velThreshold) {
        nextCollapsed = false;
      }
    }

    setIsCollapsed(nextCollapsed);
    setIsSnapping(true);
    setIsDraggingPanel(false);

    // Reset offsets on next frame so snapping stays active
    requestAnimationFrame(() => {
      setDragOffset(0);
      dragOffsetRef.current = 0;
    });

    panelDragStartRef.current = null;
  };

  const handleTouchStartDrag = (event) => {
    const t = event.touches?.[0];
    if (!t) return;
    startPanelDrag(t.clientY);
  };

  const handleTouchMoveDrag = (event) => {
    if (isDraggingPanel && event.cancelable) {
      event.preventDefault();
    }
    const t = event.touches?.[0];
    if (!t) return;
    applyPanelDrag(t.clientY);
  };

  const handleTouchEndDrag = () => {
    finishPanelDrag();
  };

  const handleHandleMouseDown = (event) => {
    startPanelDrag(event.clientY);
  };

  const handleMouseMoveDrag = (event) => {
    if (!isDraggingPanel) return;
    applyPanelDrag(event.clientY);
  };

  const handleMouseUpDrag = () => {
    if (isDraggingPanel) finishPanelDrag();
  };

  useEffect(() => {
    if (!isDraggingPanel) return;
    window.addEventListener("mousemove", handleMouseMoveDrag);
    window.addEventListener("mouseup", handleMouseUpDrag);
    window.addEventListener("touchmove", handleTouchMoveDrag, { passive: false });
    window.addEventListener("touchend", handleTouchEndDrag);
    window.addEventListener("touchcancel", handleTouchEndDrag);

    return () => {
      window.removeEventListener("mousemove", handleMouseMoveDrag);
      window.removeEventListener("mouseup", handleMouseUpDrag);
      window.removeEventListener("touchmove", handleTouchMoveDrag);
      window.removeEventListener("touchend", handleTouchEndDrag);
      window.removeEventListener("touchcancel", handleTouchEndDrag);
    };
  }, [isDraggingPanel]);

  useEffect(() => {
    if (!isSnapping) return;
    const card = cardRef.current;
    if (!card) return;
    const handleSnapEnd = (e) => {
      if (e.propertyName === "transform") {
        setIsSnapping(false);
      }
    };
    card.addEventListener("transitionend", handleSnapEnd);
    return () => {
      card.removeEventListener("transitionend", handleSnapEnd);
    };
  }, [isSnapping]);

  useEffect(() => {
    if (shouldAutoPlay && !playing) {
      forcePlay();
      if (onAutoPlayComplete) {
        onAutoPlayComplete();
      }
    }
  }, [shouldAutoPlay, playing, onAutoPlayComplete]);

  useEffect(() => {
    if (!isSticky || typeof window === "undefined") return;
    if (!window.visualViewport) return;
    if (!/CriOS/i.test(navigator.userAgent)) return;

    const updateOffset = () => {
      const layoutHeight = document.documentElement.clientHeight || window.innerHeight;
      const visualBottom =
        window.visualViewport.height + window.visualViewport.offsetTop;
      const diff = Math.max(0, visualBottom - layoutHeight);
      document.documentElement.style.setProperty("--vv-offset", `${-diff}px`);
    };

    updateOffset();
    const rafId = requestAnimationFrame(updateOffset);
    const timeoutId = window.setTimeout(updateOffset, 200);
    window.visualViewport.addEventListener("resize", updateOffset);
    window.visualViewport.addEventListener("scroll", updateOffset);

    return () => {
      cancelAnimationFrame(rafId);
      window.clearTimeout(timeoutId);
      window.visualViewport.removeEventListener("resize", updateOffset);
      window.visualViewport.removeEventListener("scroll", updateOffset);
    };
  }, [isSticky]);

  const handleContainerClick = () => {
    if (isCollapsed && !isDraggingPanel) expand();
  };

  return (
    <section
      ref={cardRef}
      className={`audio-card${isLocked ? ' audio-locked' : ''}${isSticky ? ' audio-card-sticky' : ''}${isCollapsed ? ' is-collapsed' : ''}${isDraggingPanel ? ' is-dragging' : ''}${isSnapping ? ' is-snapping' : ''}`}
      style={
        isSticky
          ? {
              "--drag-offset": `${isDraggingPanel ? dragOffset : 0}px`,
            }
          : undefined
      }
      onClick={handleContainerClick}
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
          <div
            className="audio-handle-hit"
            onTouchStart={handleTouchStartDrag}
            onMouseDown={handleHandleMouseDown}
          >
            <button
              type="button"
              className="audio-handle"
              onClick={handleHandleClick}
              onKeyDown={handleHandleKeyDown}
              aria-expanded={!isCollapsed}
              aria-label={isCollapsed ? "Expand audio controls" : "Collapse audio controls"}
            />
          </div>
        )}
        <div
          ref={controlsWrapperRef}
          className={`audio-controls-wrapper${isCollapsed ? " is-collapsed" : ""}${isDraggingPanel ? " is-dragging" : ""}`}
          style={
            isDraggingPanel
              ? (() => {
                  const maxOffset = Math.max(controlsHeightRef.current || 200, 1);
                  const currentOffset = dragOffsetRef.current || 0;
                  const progress = Math.min(Math.abs(currentOffset) / maxOffset, 1);
                  const dragOpacity = isCollapsed ? progress : 1 - progress;
                  return { "--drag-opacity": `${dragOpacity}` };
                })()
              : undefined
          }
          onTouchStart={!isSticky ? undefined : handleTouchStartDrag}
        >
          <div
            className={isSticky ? "audio-controls audio-sticky-controls" : "audio-controls"}
            onClick={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
          >
              <div className="audio-controls-row">
                <div className="audio-controls-left">
                  <span className="time-label">{fmt(current)}</span>
                  <div className="volume-control" ref={volumeControlRef}>
                    <button
                      className={`icon-btn volume-btn${muted || volume === 0 ? " is-muted" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setMuted((prev) => !prev);
                        if (voiceRef.current) voiceRef.current.muted = !muted;
                        if (bgRef.current) bgRef.current.muted = !muted;
                      }}
                      aria-expanded={false}
                      aria-label="Mute / Un-mute"
                    >
                      <img
                        src="/images/adjust-volume-audio-lesson.webp"
                        alt="Volume"
                        className="volume-icon"
                      />
                    </button>
                  </div>
                </div>

              <div className="audio-controls-center">
                <button className="icon-btn skip-btn" onClick={() => skip(-10)} title="Replay 10 s">
                  <img
                    src="/images/rewind-audio-10-seconds.webp"
                    alt="Rewind 10 seconds"
                    className="skip-icon"
                  />
                </button>
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
                <button className="icon-btn skip-btn" onClick={() => skip(10)} title="Forward 10 s">
                  <img
                    src="/images/forward-audio-10-seconds.webp"
                    alt="Forward 10 seconds"
                    className="skip-icon"
                  />
                </button>
              </div>

              <div className="audio-controls-right">
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
                <span className="time-label">{fmt(duration)}</span>
              </div>
            </div>

            <div
              className="track"
              role="slider"
              aria-valuemin={0}
              aria-valuemax={duration}
              aria-valuenow={current}
              onMouseDown={handleTrackPointerDown}
              onTouchStart={handleTrackPointerDown}
              onTouchMove={handleTrackTouchMove}
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
          </div>
        </div>
        <span className="sr-only" aria-live="polite">
          {isCollapsed ? "Audio player collapsed" : "Audio player expanded"}
        </span>
      </div>
    </section>
  );
}
