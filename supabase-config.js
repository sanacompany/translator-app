// Supabase configuration - shared across all pages
const SUPABASE_URL = 'https://bbtxfovxbqcjmyazmfhx.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_Ral_btz1s0EWfDpy6EeKJA_guVjMngC';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Free tier limits
const FREE_MONTHLY_MINUTES = 60;

// Auth helpers
async function getUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

async function getProfile(userId) {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', userId)
    .single();
  if (error) return null;
  return data;
}

async function requireAuth() {
  const user = await getUser();
  if (!user) {
    window.location.href = 'auth.html';
    return null;
  }
  return user;
}

async function signOut() {
  await supabase.auth.signOut();
  window.location.href = 'auth.html';
}

// Usage tracking
async function trackUsage(userId, seconds, mode) {
  const { data, error } = await supabase.rpc('increment_usage', {
    p_user_id: userId,
    p_seconds: seconds
  });
  return data;
}

// History helpers
async function saveToHistory(userId, sourceText, translatedText, sourceLang, targetLang, mode) {
  await supabase.from('translation_history').insert({
    user_id: userId,
    source_text: sourceText,
    translated_text: translatedText,
    source_lang: sourceLang,
    target_lang: targetLang,
    mode: mode
  });
}

async function loadHistory(userId, limit = 50) {
  const { data, error } = await supabase
    .from('translation_history')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) return [];
  return data;
}
