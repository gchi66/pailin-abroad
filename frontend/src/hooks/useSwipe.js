import { useCallback, useRef } from "react";

const useSwipe = ({ onSwipeLeft, onSwipeRight, threshold = 60 } = {}) => {
  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const deltaXRef = useRef(0);
  const deltaYRef = useRef(0);
  const isHorizontalRef = useRef(false);

  const onTouchStart = useCallback((event) => {
    if (!event.touches || event.touches.length === 0) return;
    const touch = event.touches[0];
    startXRef.current = touch.clientX;
    startYRef.current = touch.clientY;
    deltaXRef.current = 0;
    deltaYRef.current = 0;
    isHorizontalRef.current = false;
  }, []);

  const onTouchMove = useCallback((event) => {
    if (!event.touches || event.touches.length === 0) return;
    const touch = event.touches[0];
    deltaXRef.current = touch.clientX - startXRef.current;
    deltaYRef.current = touch.clientY - startYRef.current;

    if (!isHorizontalRef.current) {
      isHorizontalRef.current =
        Math.abs(deltaXRef.current) > Math.abs(deltaYRef.current);
    }

    if (isHorizontalRef.current) {
      event.preventDefault();
    }
  }, []);

  const onTouchEnd = useCallback(() => {
    const deltaX = deltaXRef.current;
    const deltaY = deltaYRef.current;
    if (
      Math.abs(deltaX) > threshold &&
      Math.abs(deltaY) < Math.abs(deltaX)
    ) {
      if (deltaX < 0) {
        onSwipeLeft?.();
      } else {
        onSwipeRight?.();
      }
    }
  }, [onSwipeLeft, onSwipeRight, threshold]);

  return { onTouchStart, onTouchMove, onTouchEnd };
};

export default useSwipe;
