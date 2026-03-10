import { useSettings } from '../contexts/SettingsContext.jsx';
export function useTheme() {
  const { state, dispatch } = useSettings();
  return {
    theme: state.theme,
    setTheme: (t) => dispatch({ type: 'SET_THEME', payload: t }),
  };
}
