import { render, screen } from "@testing-library/react";
import Download from "./Download";

test("renders a QR code linking to the public download page", () => {
  render(<Download />);

  const qrLink = screen.getByRole("link", {
    name: "เปิดหน้าดาวน์โหลด Pailin Abroad",
  });

  expect(qrLink).toHaveAttribute(
    "href",
    "https://www.pailinabroad.com/download"
  );
  expect(
    screen.getByTitle("QR code สำหรับหน้าดาวน์โหลด Pailin Abroad")
  ).toBeInTheDocument();
});

test("renders the color Pailin character", () => {
  const { container } = render(<Download />);
  const character = container.querySelector(".download-character");

  expect(character).toHaveAttribute(
    "src",
    "/images/characters/pailin-thumbs-up-head.webp"
  );
});

test("renders the feature illustrations from the app artwork", () => {
  const { container } = render(<Download />);
  const featureSources = Array.from(
    container.querySelectorAll(".download-features img")
  ).map((image) => image.getAttribute("src"));

  expect(featureSources).toEqual([
    "/images/download/ai-speaking.webp",
    "/images/download/thai-learners.webp",
    "/images/download/real-conversations.webp",
  ]);
});

test("does not offer the retired website learning experience", () => {
  render(<Download />);

  expect(
    screen.queryByRole("link", { name: "เรียนต่อบนเว็บไซต์" })
  ).not.toBeInTheDocument();
  expect(screen.queryByText("หรือดาวน์โหลดแอป")).not.toBeInTheDocument();
});
