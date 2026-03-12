require("dotenv").config({ path: "backend/.env" });

const postmark = require("postmark");
const { createClient } = require("@supabase/supabase-js");

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_KEY;
const POSTMARK_SERVER_TOKEN = process.env.POSTMARK_SERVER_TOKEN;
const POSTMARK_FROM = process.env.POSTMARK_FROM;
const TEST_EMAILS_RAW = "gchichester@gmail.com, cari.emika@yahoo.com, cwemika@gmail.com";
const TEST_EMAILS = TEST_EMAILS_RAW.split(",").map((email) => email.trim()).filter(Boolean);

const EXCLUDED_EMAILS = [
  "pailinabroad@gmail.com",
  "schafferjustin24@gmail.com"
];

function parseBool(value, defaultValue) {
  if (value == null) return defaultValue;
  return ["1", "true", "yes", "y", "on"].includes(String(value).toLowerCase());
}

const TEST_MODE = parseBool(process.env.TEST_MODE, true);

function requireEnv(name, value) {
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
}

async function sendSurveyEmails() {
  requireEnv("SUPABASE_URL", SUPABASE_URL);
  requireEnv("SUPABASE_KEY", SUPABASE_SERVICE_ROLE_KEY);
  requireEnv("POSTMARK_SERVER_TOKEN", POSTMARK_SERVER_TOKEN);
  requireEnv("POSTMARK_FROM", POSTMARK_FROM);

  if (TEST_MODE && TEST_EMAILS.length === 0) {
    throw new Error("Missing required TEST_EMAILS for test mode");
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const client = new postmark.ServerClient(POSTMARK_SERVER_TOKEN);

  let query = supabase
    .from("users")
    .select("email, username")
    .eq("is_active", true)
    .eq("is_verified", true)
    .not(
      "email",
      "in",
      `(${EXCLUDED_EMAILS.map((e) => `"${e}"`).join(",")})`
    );

  if (TEST_MODE) {
    query = supabase
      .from("users")
      .select("email, username")
      .in("email", TEST_EMAILS);
  }

  const { data: users, error } = await query;

  if (error) {
    console.error("Supabase error:", error);
    return;
  }

  const userList = TEST_MODE ? (users || []) : users;

  console.log(`Sending to ${userList.length} user(s)...`);

  for (const user of userList) {
    if (!user || !user.email) continue;
    try {
      await client.sendEmailWithTemplate({
        TemplateAlias: "feedback-survey",
        To: user.email,
        From: POSTMARK_FROM,
        TemplateModel: {
          username: user.username || "there",
        },
      });
      console.log(`Sent to ${user.email}`);
    } catch (err) {
      console.error(`Failed for ${user.email}:`, err.message || err);
    }
  }
}

sendSurveyEmails().catch((err) => {
  console.error("Script error:", err.message || err);
  process.exitCode = 1;
});
