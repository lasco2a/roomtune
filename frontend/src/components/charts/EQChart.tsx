import Plot from 'react-plotly.js';
import type { EQFilter } from '../../types';

interface EQChartProps {
  measuredFreqs: number[];
  measuredDb: number[];
  correctedDb?: number[];
  targetFreqs?: number[];
  targetDb?: number[];
  filters?: EQFilter[];
  className?: string;
  height?: number;
}

export function EQChart({
  measuredFreqs,
  measuredDb,
  correctedDb,
  targetFreqs,
  targetDb,
  className = '',
  height = 350,
}: EQChartProps) {
  const traces: Plotly.Data[] = [
    {
      x: measuredFreqs,
      y: measuredDb,
      type: 'scatter',
      mode: 'lines',
      name: 'Before EQ',
      line: { color: '#f87171', width: 1.5 },
      hovertemplate: '%{x:.0f} Hz: %{y:.1f} dB<extra></extra>',
    },
  ];

  if (correctedDb) {
    traces.push({
      x: measuredFreqs,
      y: correctedDb,
      type: 'scatter',
      mode: 'lines',
      name: 'After EQ',
      line: { color: '#34d399', width: 2 },
      hovertemplate: '%{x:.0f} Hz: %{y:.1f} dB<extra></extra>',
    });
  }

  if (targetFreqs && targetDb) {
    traces.push({
      x: targetFreqs,
      y: targetDb,
      type: 'scatter',
      mode: 'lines',
      name: 'Target',
      line: { color: '#f97316', width: 2, dash: 'dash' },
      hovertemplate: '%{x:.0f} Hz: %{y:.1f} dB<extra></extra>',
    });
  }

  return (
    <div className={className}>
      <Plot
        data={traces}
        layout={{
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
          yaxis: { title: { text: 'dB' }, gridcolor: 'rgba(75,85,99,0.3)', dtick: 6 },
          legend: { x: 0, y: 1, bgcolor: 'transparent', font: { size: 10 } },
          height,
          hovermode: 'x unified' as const,
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%' }}
      />
    </div>
  );
}
