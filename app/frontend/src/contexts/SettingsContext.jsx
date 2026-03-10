import React, { createContext, useContext, useEffect, useReducer } from 'react';
import { toast } from 'sonner';
import { fetchProfiles, fetchModelConfig } from '../api/config.js';
import { DEFAULT_GPU_VRAM } from '../constants/defaults.js';

const PROFILE_FALLBACK = [{ id: 'general', name: 'General', description: '通用翻譯' }];

const SettingsContext = createContext(null);

function settingsReducer(state, action) {
  switch (action.type) {
    case 'SET_THEME': return { ...state, theme: action.payload };
    case 'SET_LANGUAGE': return { ...state, uiLanguage: action.payload };
    case 'SET_GPU_VRAM': return { ...state, gpuVram: action.payload };
    case 'SET_PROFILES': return { ...state, profiles: action.payload };
    case 'SET_MODEL_CONFIG': return { ...state, modelConfig: action.payload };
    case 'SET_DEFAULT_SRC_LANG': return { ...state, defaultSrcLang: action.payload };
    case 'SET_DEFAULT_TARGETS': return { ...state, defaultTargets: action.payload };
    case 'SET_NUM_CTX': return { ...state, numCtx: action.payload };
    default: return state;
  }
}

function loadFromStorage(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}

export function SettingsProvider({ children }) {
  const [state, dispatch] = useReducer(settingsReducer, {
    theme: loadFromStorage('theme', 'system'),
    uiLanguage: loadFromStorage('uiLanguage', 'zh-TW'),
    gpuVram: loadFromStorage('gpuVram', DEFAULT_GPU_VRAM),
    profiles: PROFILE_FALLBACK,
    modelConfig: [],
    defaultSrcLang: loadFromStorage('defaultSrcLang', 'auto'),
    defaultTargets: loadFromStorage('defaultTargets', []),
    numCtx: null,
  });

  useEffect(() => {
    async function init() {
      try {
        const profiles = await fetchProfiles();
        dispatch({ type: 'SET_PROFILES', payload: profiles });
      } catch (err) {
        dispatch({ type: 'SET_PROFILES', payload: PROFILE_FALLBACK });
        toast.error(`無法載入翻譯情境: ${err.message}`);
      }
      const modelConfig = await fetchModelConfig();
      dispatch({ type: 'SET_MODEL_CONFIG', payload: modelConfig });
    }
    init();
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    if (state.theme === 'dark') html.setAttribute('data-theme', 'dark');
    else if (state.theme === 'light') html.removeAttribute('data-theme');
    else {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      if (mq.matches) html.setAttribute('data-theme', 'dark');
      else html.removeAttribute('data-theme');
    }
    localStorage.setItem('theme', JSON.stringify(state.theme));
  }, [state.theme]);

  useEffect(() => { localStorage.setItem('gpuVram', JSON.stringify(state.gpuVram)); }, [state.gpuVram]);
  useEffect(() => { localStorage.setItem('uiLanguage', JSON.stringify(state.uiLanguage)); }, [state.uiLanguage]);

  return <SettingsContext.Provider value={{ state, dispatch }}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
