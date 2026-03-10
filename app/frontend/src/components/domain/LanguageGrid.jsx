import React, { useState } from 'react';
import { TARGET_LANGUAGES, LANG_GROUPS } from '../../constants/languages.js';
import { Checkbox } from '../ui/Checkbox.jsx';

export function LanguageGrid({ selected, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const ALL = expanded
    ? Object.values(LANG_GROUPS).flat().map(id => ({ id, label: id }))
    : TARGET_LANGUAGES;

  return (
    <div className="language-grid-wrapper">
      <div className="language-grid">
        {ALL.map(lang => (
          <Checkbox
            key={lang.id}
            label={lang.label}
            checked={selected.includes(lang.id)}
            onChange={e => {
              if (e.target.checked) onChange([...selected, lang.id]);
              else onChange(selected.filter(l => l !== lang.id));
            }}
          />
        ))}
      </div>
      <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(v => !v)}>
        {expanded ? '收起語言列表' : '展開完整語言列表'}
      </button>
    </div>
  );
}
