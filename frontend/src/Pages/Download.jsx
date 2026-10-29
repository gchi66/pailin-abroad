import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  APP_STORE_URL,
  PLAY_STORE_URL,
  getMobileStore,
} from "../lib/appStores";
import "../Styles/Download.css";

const DOWNLOAD_URL = "https://www.pailinabroad.com/download";

const FEATURES = [
  {
    image: "/images/download/ai-speaking.webp",
    title: "ฝึกพูดกับ AI พร้อมรับคำแนะนำ",
    description: "ฝึกออกเสียง พร้อมรับคำแนะนำทันที",
  },
  {
    image: "/images/download/thai-learners.webp",
    title: "สร้างมาเพื่อคนไทยโดยเฉพาะ",
    description: "เรียนรู้และแก้ข้อผิดพลาดที่คนไทยมักเจอ",
  },
  {
    image: "/images/download/real-conversations.webp",
    title: "บทสนทนาที่ใช้จริง",
    description: "ฝึกภาษาอังกฤษผ่านเรื่องราวของไพลิน",
  },
];

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 15.5v2.25A2.25 2.25 0 0 0 7.25 20h9.5A2.25 2.25 0 0 0 19 17.75V15.5" />
    </svg>
  );
}

export default function Download() {
  const [mobileStoreUrl, setMobileStoreUrl] = useState(null);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "ดาวน์โหลด Pailin Abroad";

    const store = getMobileStore(
      navigator.userAgent,
      navigator.platform,
      navigator.maxTouchPoints
    );
    setMobileStoreUrl(
      store === "android"
        ? PLAY_STORE_URL
        : store === "ios"
          ? APP_STORE_URL
          : null
    );

    return () => {
      document.title = previousTitle;
    };
  }, []);

  return (
    <main className="download-page">
      <section className="download-card" aria-labelledby="download-title">
        <img
          className="download-logo"
          src="/images/full-logo.webp"
          alt="Pailin Abroad"
        />

        <header className="download-hero">
          <div className="download-heading">
            <h1 id="download-title">อังกฤษติดปาก</h1>
            <p>
              ฝึกภาษาอังกฤษให้เป็นธรรมชาติ
              <br />
              ผ่านบทสนทนาที่ใช้จริง
            </p>
          </div>
          <img
            className="download-character"
            src="/images/characters/pailin-thumbs-up-head.webp"
            alt=""
          />
        </header>

        <div className="download-actions">
          <div className="download-qr">
            <a href={DOWNLOAD_URL} aria-label="เปิดหน้าดาวน์โหลด Pailin Abroad">
              <QRCodeSVG
                value={DOWNLOAD_URL}
                size={160}
                level="M"
                marginSize={1}
                title="QR code สำหรับหน้าดาวน์โหลด Pailin Abroad"
              />
            </a>
            <span>สแกนด้วยมือถือ</span>
          </div>

          {mobileStoreUrl ? (
            <a className="download-primary-button" href={mobileStoreUrl}>
              <span>ดาวน์โหลดแอปฟรี</span>
              <DownloadIcon />
            </a>
          ) : (
            <details className="download-desktop-cta">
              <summary className="download-primary-button">
                <span>ดาวน์โหลดแอปฟรี</span>
                <DownloadIcon />
              </summary>
              <div className="download-store-links" aria-label="เลือกร้านค้าแอป">
                <a href={APP_STORE_URL}>ดาวน์โหลดบน App Store</a>
                <a href={PLAY_STORE_URL}>ดาวน์โหลดบน Google Play</a>
              </div>
            </details>
          )}
        </div>

        <ul className="download-features" aria-label="จุดเด่นของ Pailin Abroad">
          {FEATURES.map((feature) => (
            <li key={feature.title}>
              <img src={feature.image} alt="" />
              <div>
                <strong>{feature.title}</strong>
                <p>{feature.description}</p>
              </div>
            </li>
          ))}
        </ul>

        <p className="download-tagline">
          Real-world English, made for Thai speakers
        </p>
      </section>
    </main>
  );
}
