interface LevelMeterProps {
  rmsDb: number;
  peakDb: number;
  clipped: boolean;
  minDb?: number;
  maxDb?: number;
}

export function LevelMeter({
  rmsDb,
  peakDb,
  clipped,
  minDb = -60,
  maxDb = 0,
}: LevelMeterProps) {
  const range = maxDb - minDb;
  const rmsPct = Math.max(0, Math.min(100, ((rmsDb - minDb) / range) * 100));
  const peakPct = Math.max(0, Math.min(100, ((peakDb - minDb) / range) * 100));

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>Level</span>
        <span className={clipped ? 'font-bold text-red-400' : ''}>
          {peakDb > -120 ? `${peakDb.toFixed(1)} dBFS` : '---'}
          {clipped && ' CLIP'}
        </span>
      </div>
      <div className="relative h-4 overflow-hidden rounded-full bg-gray-800">
        {/* RMS bar */}
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-75"
          style={{ width: `${rmsPct}%` }}
        />
        {/* Peak marker */}
        <div
          className={`absolute inset-y-0 w-0.5 transition-all duration-75 ${
            clipped ? 'bg-red-500' : 'bg-white/80'
          }`}
          style={{ left: `${peakPct}%` }}
        />
        {/* Scale markers */}
        <div className="absolute inset-0 flex items-center justify-between px-1">
          {[-48, -36, -24, -12, -6, 0].map((db) => {
            const pct = ((db - minDb) / range) * 100;
            return (
              <div
                key={db}
                className="absolute h-full w-px bg-gray-700/50"
                style={{ left: `${pct}%` }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
