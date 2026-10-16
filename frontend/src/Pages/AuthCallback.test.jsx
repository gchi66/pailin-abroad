import { render, screen } from "@testing-library/react";
import AuthCallback from "./AuthCallback";

afterEach(() => {
  window.history.replaceState({}, "", "/");
});

test("passes the untouched authentication code back to the mobile app", () => {
  window.history.replaceState({}, "", "/auth/callback?code=one-time-code");

  render(<AuthCallback />);

  expect(
    screen.getByRole("link", { name: "เปิดแอป Pailin Abroad" })
  ).toHaveAttribute(
    "href",
    "pailinabroadmobile://auth/callback?code=one-time-code"
  );
  expect(screen.getByRole("link", { name: "ดาวน์โหลดแอป" })).toHaveAttribute(
    "href",
    "/download"
  );
});

test("does not offer an app handoff for an invalid callback", () => {
  window.history.replaceState(
    {},
    "",
    "/auth/callback?error=access_denied&error_description=Link%20expired"
  );

  render(<AuthCallback />);

  expect(screen.getByText("Link expired")).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "เปิดแอป Pailin Abroad" })
  ).not.toBeInTheDocument();
});

test("preserves token callbacks in the app handoff URL", () => {
  window.history.replaceState(
    {},
    "",
    "/auth/callback#access_token=access-token&refresh_token=refresh-token&type=signup"
  );

  render(<AuthCallback />);

  expect(
    screen.getByRole("link", { name: "เปิดแอป Pailin Abroad" })
  ).toHaveAttribute(
    "href",
    "pailinabroadmobile://auth/callback#access_token=access-token&refresh_token=refresh-token&type=signup"
  );
});
