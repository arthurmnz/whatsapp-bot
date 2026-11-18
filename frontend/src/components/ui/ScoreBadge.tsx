import React from 'react';
import { getScoreTone } from '../../lib/format';

export const ScoreBadge: React.FC<{ score: number; suffix?: string }> = ({
  score,
  suffix = '%',
}) => {
  const tone = getScoreTone(score);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-xs font-semibold tabular-nums ${tone.badgeClass}`}
    >
      {score}
      {suffix}
    </span>
  );
};

export const SkeletonBlock: React.FC<{ className?: string }> = ({ className = 'h-4 w-full' }) => (
  <div className={`animate-pulse rounded-md bg-slate-800/75 ${className}`} aria-hidden="true" />
);
