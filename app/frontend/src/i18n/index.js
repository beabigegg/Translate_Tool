import { useSettings } from '../contexts/SettingsContext.jsx';
import zhTW from './zh-TW.js';
import en from './en.js';

const TRANSLATIONS = { 'zh-TW': zhTW, en };

export function useTranslation() {
  const { state } = useSettings();
  const t = TRANSLATIONS[state.uiLanguage] || TRANSLATIONS['zh-TW'];
  return { t: (key) => t[key] ?? key };
}
