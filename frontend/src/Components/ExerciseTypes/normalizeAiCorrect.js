export function normalizeAiCorrect(value) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "1"].includes(normalized)) {
      return true;
    }
    if (["false", "no", "0"].includes(normalized)) {
      return false;
    }
    return false;
  }

  if (typeof value === "number") {
    return value >= 0.5;
  }

  return Boolean(value);
}
