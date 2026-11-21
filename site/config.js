// Ligação ao Supabase (valores públicos: a "anon key" só dá acesso ao que as regras RLS permitem).
// Vazio = a página lê data/races.json e guarda o calendário só no browser.
window.CALENDARIO_CONFIG = {
  supabaseUrl: "https://wtgjdtzvcogfsrhgixgv.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0Z2pkdHp2Y29nZnNyaGdpeGd2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUyNzM5MzYsImV4cCI6MjExMDg0OTkzNn0.k3t4t6vm4FN8gOCRhwtgEk-6ak5DJZ5Pfw88MB_xNbg",
};
