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
