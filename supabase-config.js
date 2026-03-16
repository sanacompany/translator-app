// Supabase configuration - shared across all pages
const SUPABASE_URL = 'https://bbtxfovxbqcjmyazmfhx.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJidHhmb3Z4YnFjam15YXptZmh4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0MjQ3MzcsImV4cCI6MjA4OTAwMDczN30.bPYNBtfUcNPU5-XqzFryPmHd4W7LBb8aKMHGEcBI_YA';

const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Free tier limits
const FREE_MONTHLY_MINUTES = 60;

// Auth helpers
async function getUser() {
  const { data: { user } } = await sb.auth.getUser();
  return user;
}

async function getProfile(userId) {
  const { data, error } = await sb
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
  await sb.auth.signOut();
  window.location.href = 'auth.html';
}

// Usage tracking
async function trackUsage(userId, seconds, mode) {
  const { data, error } = await sb.rpc('increment_usage', {
    p_user_id: userId,
    p_seconds: seconds
  });
  return data;
}

// History helpers
async function saveToHistory(userId, sourceText, translatedText, sourceLang, targetLang, mode) {
  await sb.from('translation_history').insert({
    user_id: userId,
    source_text: sourceText,
    translated_text: translatedText,
    source_lang: sourceLang,
    target_lang: targetLang,
    mode: mode
  });
}

async function loadHistory(userId, limit = 50) {
  const { data, error } = await sb
    .from('translation_history')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) return [];
  return data;
}
