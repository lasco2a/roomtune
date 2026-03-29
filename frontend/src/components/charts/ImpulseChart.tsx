import Plot from 'react-plotly.js';

interface ImpulseChartProps {
  time: number[];
  amplitude: number[];
  className?: string;
  height?: number;
}

export function ImpulseChart({ time, amplitude, className = '', height = 250 }: ImpulseChartProps) {
  return (
    <div className={className}>
      <Plot
        data={[
          {
            x: time,
            y: amplitude,
            type: 'scatter',
            mode: 'lines',
            name: 'Impulse Response',
            line: { color: '#818cf8', width: 1 },
          },
        ]}
        layout={{
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'rgba(17,24,39,0.6)',
          font: { color: '#9ca3af', size: 11 },
          margin: { t: 20, r: 20, b: 50, l: 60 },
          xaxis: { title: { text: 'Time (ms)' }, gridcolor: 'rgba(75,85,99,0.3)' },
          yaxis: { title: { text: 'Amplitude' }, gridcolor: 'rgba(75,85,99,0.3)' },
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
