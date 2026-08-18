export const APP_STORE_URL =
  "https://apps.apple.com/th/app/pailin-abroad/id6762322535";

export const PLAY_STORE_URL =
  "https://play.google.com/store/apps/details?id=com.pailinabroad.app&hl=th";

export function getMobileStore(userAgent, platform, maxTouchPoints) {
  const ua = userAgent || "";

  if (/android/i.test(ua)) return "android";

  // iPadOS can identify itself as macOS when desktop-class browsing is enabled.
  const isAppleMobile = /iPad|iPhone|iPod/i.test(ua);
  const isIPadDesktopMode = platform === "MacIntel" && maxTouchPoints > 1;
  return isAppleMobile || isIPadDesktopMode ? "ios" : null;
}

export function getStoreForCurrentDevice() {
  if (typeof navigator === "undefined") return null;

  return getMobileStore(
    navigator.userAgent,
    navigator.platform,
    navigator.maxTouchPoints
  );
}

export function getStoreUrl(store) {
  if (store === "android") return PLAY_STORE_URL;
  if (store === "ios") return APP_STORE_URL;
  return null;
}
