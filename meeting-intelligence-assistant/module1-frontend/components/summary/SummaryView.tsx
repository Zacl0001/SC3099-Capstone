import type { Summary } from '@/lib/types';

export default function SummaryView({ summary }: { summary: Summary }) {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Executive summary</h3>
        <p className="mt-2 leading-relaxed whitespace-pre-line text-slate-800">{summary.summary}</p>
      </section>

      {summary.key_points.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Key points</h3>
          <ul className="mt-2 space-y-2">
            {summary.key_points.map((point, i) => (
              <li key={i} className="flex gap-3 text-slate-800">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden="true" />
                <span className="leading-relaxed">{point}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {summary.topics && summary.topics.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Topics discussed</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {summary.topics.map((topic) => (
              <li key={topic} className="rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700">
                {topic}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
