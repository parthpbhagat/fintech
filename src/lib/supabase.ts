import { createClient } from '@supabase/supabase-js';

// Replace these with your actual Supabase credentials if you have them.
// Otherwise, the application will fallback to mock data.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co';
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key';

export const supabase = createClient(supabaseUrl, supabaseKey);

export const fetchCompaniesFromDB = async () => {
  try {
    const { data, error } = await supabase
      .from('companies')
      .select('*');
    
    if (error) throw error;
    return data;
  } catch (error) {
    console.error('Error fetching from SQL Server/DB:', error);
    return null;
  }
};
