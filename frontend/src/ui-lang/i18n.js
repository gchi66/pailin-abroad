export const copy = {
  nav: {
    home: { en: "HOME", th: "หน้าแรก" },
    about: { en: "ABOUT", th: "เกี่ยวกับ" },
    lessons: { en: "LESSONS", th: "บทเรียน" },
    resources: { en: "RESOURCES", th: "แหล่งข้อมูล" },
    contact: { en: "CONTACT", th: "ติดต่อ" },
    pricing: { en: "PRICING", th: "ราคา" },
    myPathway: { en: "MY PATHWAY", th: "เส้นทางของฉัน" },
  },
  uiLabel: { en: "UI:", th: "ภาษา:" },
  topicLibraryPage: {
    title: { en: "TOPIC LIBRARY", th: "คลังหัวข้อ" },
    subtitle: {
      en: "Further explanations on a range of interesting ESL topics",
      th: "คำอธิบายเพิ่มเติมเกี่ยวกับหัวข้อภาษาอังกฤษ ESL ที่น่าสนใจหลากหลาย",
    },
    loading: { en: "Loading topics...", th: "กำลังโหลดหัวข้อ..." },
    emptyTitle: { en: "No topics available yet", th: "ยังไม่มีหัวข้อ" },
    emptyBody: {
      en: "Topics will appear here when they are added to the library.",
      th: "หัวข้อจะปรากฏที่นี่เมื่อมีการเพิ่มเข้าในคลัง",
    },
    errorTitle: { en: "Topic Library", th: "คลังหัวข้อ" },
  },
  topicDetailPage: {
    loadingTitle: { en: "Loading...", th: "กำลังโหลด..." },
    loadingBody: { en: "Loading topic content...", th: "กำลังโหลดเนื้อหาหัวข้อ..." },
    notFoundTitle: { en: "Topic Not Found", th: "ไม่พบหัวข้อ" },
    notFoundBody: { en: "Topic not found", th: "ไม่พบหัวข้อ" },
    backToLibrary: { en: "← Back to Topic Library", th: "← กลับไปยังคลังหัวข้อ" },
    emptyContent: { en: "No content available for this topic yet.", th: "ยังไม่มีเนื้อหาสำหรับหัวข้อนี้" },
  },
};

export function t(path, ui = "en") {
  // path like "nav.home" or "uiLabel"
  const parts = path.split(".");
  let node = copy;
  for (const p of parts) node = node?.[p];
  if (!node) return "";
  if (typeof node === "string") return node; // already a leaf
  return node[ui] ?? node.en ?? "";
}
