import Plot from 'react-plotly.js';
import type { FrequencyResponse } from '../../types';

interface FrequencyChartProps {
  responses: { data: FrequencyResponse; label: string; color?: string }[];
  target?: { frequencies: number[]; amplitude_db: number[]; label?: string };
  smoothing?: string;
  className?: string;
  height?: number;
}

const DARK_LAYOUT: Partial<Plotly.Layout> = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(17,24,39,0.6)',
  font: { color: '#9ca3af', size: 11 },
  margin: { t: 30, r: 20, b: 50, l: 60 },
  xaxis: {
    type: 'log',
    title: { text: 'Frequency (Hz)' },
    range: [Math.log10(20), Math.log10(20000)],
    gridcolor: 'rgba(75,85,99,0.3)',
    tickvals: [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
    ticktext: ['20', '50', '100', '200', '500', '1k', '2k', '5k', '10k', '20k'],
  },
  yaxis: {
    title: { text: 'dB SPL (relative)' },
    gridcolor: 'rgba(75,85,99,0.3)',
    dtick: 6,
  },
  legend: { x: 0, y: 1, bgcolor: 'transparent', font: { size: 10 } },
  hovermode: 'x unified' as const,
};

const COLORS = ['#818cf8', '#34d399', '#f59e0b', '#f87171', '#a78bfa', '#22d3ee'];

export function FrequencyChart({
  responses,
  target,
  className = '',
  height = 350,
}: FrequencyChartProps) {
  const traces: Plotly.Data[] = responses.map((r, i) => ({
    x: r.data.frequencies,
    y: r.data.magnitude_db,
    type: 'scatter' as const,
    mode: 'lines' as const,
    name: r.label,
    line: { color: r.color || COLORS[i % COLORS.length], width: 1.5 },
    hovertemplate: '%{x:.0f} Hz: %{y:.1f} dB<extra></extra>',
  }));

  if (target) {
    traces.push({
      x: target.frequencies,
      y: target.amplitude_db,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: target.label || 'Target',
      line: { color: '#f97316', width: 2, dash: 'dash' },
      hovertemplate: '%{x:.0f} Hz: %{y:.1f} dB<extra></extra>',
    });
  }

  return (
    <div className={className}>
      <Plot
        data={traces}
        layout={{ ...DARK_LAYOUT, height }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%' }}
      />
    </div>
  );
}
