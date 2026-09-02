'use client';

import { ReactNode, createContext, useContext, useEffect, useState } from 'react';

import {
  DEFAULT_THEME,
  THEME_COOKIE_NAME,
  THEME_PREFERENCE_COOKIE,
  THEME_PREFERENCE_VERSION
} from './theme.config';

function setThemeCookie(theme: string) {
  if (typeof window === 'undefined') return;

  const cookieOptions = `path=/; max-age=31536000; SameSite=Lax; ${window.location.protocol === 'https:' ? 'Secure;' : ''}`;
  document.cookie = `${THEME_COOKIE_NAME}=${theme}; ${cookieOptions}`;
  document.cookie = `${THEME_PREFERENCE_COOKIE}=${THEME_PREFERENCE_VERSION}; ${cookieOptions}`;
}

type ThemeContextType = {
  activeTheme: string;
  setActiveTheme: (theme: string) => void;
};

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ActiveThemeProvider({
  children,
  initialTheme
}: {
  children: ReactNode;
  initialTheme?: string;
}) {
  const themeToUse = initialTheme || DEFAULT_THEME;
  const [activeTheme, setActiveTheme] = useState<string>(themeToUse);

  useEffect(() => {
    // Only update if theme has changed
    const currentTheme = document.documentElement.getAttribute('data-theme');
    if (currentTheme !== activeTheme) {
      setThemeCookie(activeTheme);

      // Remove existing data-theme attribute
      document.documentElement.removeAttribute('data-theme');

      // Remove any theme classes from body (cleanup)
      Array.from(document.body.classList)
        .filter((className) => className.startsWith('theme-'))
        .forEach((className) => {
          document.body.classList.remove(className);
        });

      // Set data-theme on html element
      if (activeTheme) {
        document.documentElement.setAttribute('data-theme', activeTheme);
      }
    } else {
      // Still update cookie in case it's missing
      setThemeCookie(activeTheme);
    }
  }, [activeTheme]);

  return (
    <ThemeContext.Provider value={{ activeTheme, setActiveTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useThemeConfig() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useThemeConfig must be used within an ActiveThemeProvider');
  }
  return context;
}
