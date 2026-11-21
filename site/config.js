// Ligação ao Supabase (valores públicos: a "anon key" só dá acesso ao que as regras RLS permitem).
// Vazio = a página lê data/races.json e guarda o calendário só no browser.
window.CALENDARIO_CONFIG = {
  supabaseUrl: "",
  supabaseAnonKey: "",
};
