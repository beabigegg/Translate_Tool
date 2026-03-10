export const TARGET_LANGUAGES = [
  { id: 'English', label: 'English 英語' },
  { id: 'Vietnamese', label: 'Vietnamese 越南語' },
  { id: 'Thai', label: 'Thai 泰語' },
  { id: 'Japanese', label: 'Japanese 日語' },
  { id: 'Korean', label: 'Korean 韓語' },
  { id: 'Indonesian', label: 'Indonesian 印尼語' },
  { id: 'Traditional Chinese', label: 'Traditional Chinese 繁體中文' },
  { id: 'Simplified Chinese', label: 'Simplified Chinese 簡體中文' },
];

export const LANG_GROUPS = {
  'East Asian': ['English', 'Traditional Chinese', 'Simplified Chinese', 'Japanese', 'Korean'],
  'Southeast Asian': ['Vietnamese', 'Thai', 'Indonesian', 'Malay', 'Filipino', 'Burmese', 'Khmer', 'Lao'],
  'South Asian': ['Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi', 'Urdu', 'Nepali', 'Sinhala'],
  'Western European': ['French', 'German', 'Spanish', 'Portuguese', 'Italian', 'Dutch'],
  'Northern European': ['Swedish', 'Norwegian', 'Danish', 'Finnish', 'Icelandic'],
  'Eastern European': ['Russian', 'Polish', 'Ukrainian', 'Czech', 'Romanian', 'Hungarian', 'Bulgarian', 'Slovak', 'Croatian', 'Serbian', 'Slovenian', 'Lithuanian', 'Latvian', 'Estonian'],
  'Southern European': ['Greek', 'Turkish'],
  'Middle Eastern': ['Arabic', 'Hebrew', 'Persian'],
};

export const ALL_LANGUAGES = ['auto', ...Object.values(LANG_GROUPS).flat()];
