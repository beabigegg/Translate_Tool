// Node 26 exposes an experimental-but-non-functional localStorage global that
// shadows jsdom's implementation. Replace it with a working in-memory stub so
// component code that calls localStorage.getItem / setItem / clear works in tests.
const _store = {};
vi.stubGlobal('localStorage', {
  getItem: (key) => Object.prototype.hasOwnProperty.call(_store, key) ? _store[key] : null,
  setItem: (key, value) => { _store[key] = String(value); },
  removeItem: (key) => { delete _store[key]; },
  clear: () => { Object.keys(_store).forEach(k => delete _store[k]); },
  get length() { return Object.keys(_store).length; },
  key: (i) => Object.keys(_store)[i] ?? null,
});

// jsdom does not implement window.matchMedia (used by SettingsContext theme detection).
// Stub it with a minimal no-op so tests don't throw.
vi.stubGlobal('matchMedia', (query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
}));
