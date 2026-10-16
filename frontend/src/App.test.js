import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

jest.mock("./Components/LegalPage", () => () => <main>Legal page</main>);

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

test.each([
  "/",
  "/lessons",
  "/membership",
  "/checkout",
  "/payment-success",
  "/profile",
  "/onboarding",
  "/some-unknown-page",
])("redirects %s to the download page", async (path) => {
  window.history.replaceState({}, "", path);

  render(<App />);

  await waitFor(() => {
    expect(window.location.pathname).toBe("/download");
  });
  expect(
    screen.getByRole("link", { name: "ดาวน์โหลดบน App Store" })
  ).toBeInTheDocument();
});

test("keeps the mobile authentication callback open", () => {
  window.history.replaceState({}, "", "/auth/callback?code=one-time-code");

  render(<App />);

  expect(window.location.pathname).toBe("/auth/callback");
  expect(
    screen.getByRole("link", { name: "เปิดแอป Pailin Abroad" })
  ).toHaveAttribute(
    "href",
    "pailinabroadmobile://auth/callback?code=one-time-code"
  );
});

test.each(["/contact", "/terms", "/privacy", "/delete-account"])(
  "keeps %s publicly accessible",
  (path) => {
    window.history.replaceState({}, "", path);

    render(<App />);

    expect(window.location.pathname).toBe(path);
    expect(
      screen.queryByRole("link", { name: "ดาวน์โหลดบน App Store" })
    ).not.toBeInTheDocument();
  }
);
