import { createClient} from '@supabase/supabase-js';

// Environment variables for sensitive configuration
const SUPABASE_URL = process.env.REACT_APP_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.REACT_APP_SUPABASE_ANON_KEY;

// The web auth callback is now only a bridge back into the mobile app. Do not
// let the browser consume its one-time code before the app receives it.
const isMobileAuthBridge =
  typeof window !== "undefined" &&
  window.location.pathname.replace(/\/+$/, "") === "/auth/callback";

// Initialize the Supabase client
const supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    detectSessionInUrl: !isMobileAuthBridge,
  },
});


// Named export for checking if a user is logged in
export const isUserLoggedIn = () => {
  const session = supabaseClient.auth.session(); // Check for the session
  return session?.user || null; // Return the logged-in user or null
};

// Default export for Supabase client
export default supabaseClient;
