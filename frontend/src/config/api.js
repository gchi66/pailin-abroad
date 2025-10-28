// Centralised API base URL resolution with sensible fallbacks for local dev environments.
const ENV_BASE_URL = (process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_API_URL || "").trim();
const DEV_PORT = (process.env.REACT_APP_DEV_API_PORT || "5000").trim();

function buildLocalBaseUrl() {
  const defaultUrl = `http://127.0.0.1:${DEV_PORT}`;

  if (typeof window === "undefined") {
    return defaultUrl;
  }

  const { protocol, hostname } = window.location;
  const safeProtocol = protocol && protocol.startsWith("http") ? protocol : "http:";

  const loopbackHosts = new Set(["localhost", "127.0.0.1", "::1"]);
  const privateIpPattern = /^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)/;
  const isPrivateNetwork = privateIpPattern.test(hostname || "");

  const targetHost = loopbackHosts.has(hostname) || isPrivateNetwork ? hostname : "127.0.0.1";

  return `${safeProtocol}//${targetHost || "127.0.0.1"}:${DEV_PORT}`;
}

export const API_BASE_URL = ENV_BASE_URL || buildLocalBaseUrl();
