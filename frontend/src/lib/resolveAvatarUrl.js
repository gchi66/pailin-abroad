const AVATAR_WEBP_PATTERN = /\/images\/characters\/avatar_\d+\.webp(\?.*)?$/;

export const resolveAvatarUrl = (url = "") => {
  if (!url) return url;
  if (typeof navigator === "undefined") return url;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent || "");
  if (!isIOS) return url;
  if (!AVATAR_WEBP_PATTERN.test(url)) return url;
  return url.replace(/\.webp(\?.*)?$/, ".png$1");
};
