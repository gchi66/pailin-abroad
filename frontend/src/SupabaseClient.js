import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://<your-supabase-project>.supabase.co';
const supabaseKey = '<your-anon-public-key>';

export const supabase = createClient(supabaseUrl, supabaseKey);
