/**
 * Default theme that loads when no user preference is set
 * Change this value to set a different default theme
 */
export const DEFAULT_THEME = 'supabase';
export const THEME_COOKIE_NAME = 'active_theme';
export const THEME_PREFERENCE_COOKIE = 'active_theme_preference';
// Bump this when the template's shipped default changes. Existing Vercel
// cookies from the migration build are defaults, not an explicit choice.
export const THEME_PREFERENCE_VERSION = '3';

export const THEMES = [
  {
    name: 'Claude',
    value: 'claude'
  },
  {
    name: 'Discord',
    value: 'discord'
  },
  {
    name: 'Supabase',
    value: 'supabase'
  },
  {
    name: 'Vercel',
    value: 'vercel'
  },
  {
    name: 'Mono',
    value: 'mono'
  },
  {
    name: 'Notebook',
    value: 'notebook'
  },
  {
    name: 'Light Green',
    value: 'light-green'
  },
  {
    name: 'Zen',
    value: 'zen'
  },
  {
    name: 'Astro Vista',
    value: 'astro-vista'
  },
  {
    name: 'WhatsApp',
    value: 'whatsapp'
  }
];
