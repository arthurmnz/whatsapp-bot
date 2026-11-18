import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';

interface TagInputProps {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  hint?: string;
  tone?: 'default' | 'danger' | 'accent';
}

export const TagInput: React.FC<TagInputProps> = ({
  label,
  values,
  onChange,
  placeholder = 'Digite e pressione Enter',
  hint,
  tone = 'default',
}) => {
  const [draft, setDraft] = useState('');

  const addTokens = (raw: string) => {
    const tokens = raw
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    if (!tokens.length) return;

    const existingLower = new Set(values.map((v) => v.toLowerCase()));
    const next = [...values];
    for (const token of tokens) {
      if (!existingLower.has(token.toLowerCase())) {
        existingLower.add(token.toLowerCase());
        next.push(token);
      }
    }
    onChange(next);
    setDraft('');
  };

  const removeAt = (index: number) => {
    onChange(values.filter((_, idx) => idx !== index));
  };

  const pillClass =
    tone === 'danger'
      ? 'border-rose-500/35 bg-rose-500/12 text-rose-200'
      : tone === 'accent'
        ? 'border-emerald-500/35 bg-emerald-500/12 text-emerald-200'
        : 'border-slate-700 bg-slate-800/80 text-slate-200';

  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-300">{label}</label>
      <div className="rounded-lg border border-slate-700/80 bg-[#0d111a] p-2 transition-colors focus-within:border-sky-500/70">
        {values.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {values.map((val, idx) => (
              <span
                key={`${val}-${idx}`}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${pillClass}`}
              >
                <span>{val}</span>
                <button
                  type="button"
                  onClick={() => removeAt(idx)}
                  className="rounded p-0.5 opacity-75 transition-opacity hover:opacity-100"
                  aria-label={`Remover ${val}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addTokens(draft);
              } else if (e.key === 'Backspace' && !draft && values.length > 0) {
                removeAt(values.length - 1);
              }
            }}
            onBlur={() => {
              if (draft.trim()) addTokens(draft);
            }}
            placeholder={placeholder}
            className="min-w-0 flex-1 bg-transparent px-1.5 py-1 text-sm text-slate-100 placeholder-[#8896ab] focus:outline-none"
          />
          {draft.trim() && (
            <button
              type="button"
              onClick={() => addTokens(draft)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
            >
              <Plus className="h-3 w-3" />
              Adicionar
            </button>
          )}
        </div>
      </div>
      {hint && <p className="text-[11px] text-[#8896ab]">{hint}</p>}
    </div>
  );
};
