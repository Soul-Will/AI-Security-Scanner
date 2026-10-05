import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://lwhnpznqkxehedrgsucn.supabase.co";
// [MVP NOTE]: Temporarily using Service Role Key to bypass RLS for local dev without auth
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx3aG5wem5xa3hlaGVkcmdzdWNuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTI1MTI4MCwiZXhwIjoyMTAwODI3MjgwfQ.dTuAvz-jNus40DQ5FWhzKQz7oxtw2K1FYm9ovDZjm8A";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
