import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis } from 'recharts'
import { AXIS_STYLE, Card, COLORS, GRID_STYLE } from './ChartKit'

/**
 * Renders a scatter plot for two numeric columns that show a real
 * statistical relationship (e.g. Unit Cost vs Retail Price) — backend only
 * sends this when a correlation was actually detected, so it never appears
 * for unrelated number pairs.
 */
export default function ScatterChartCard({ correlationChart, records }) {
  if (!correlationChart) return null
  const { x_column, y_column, x_label, y_label, title, description, correlation } = correlationChart

  const points = records
    .filter((r) => typeof r[x_column] === 'number' && typeof r[y_column] === 'number')
    .slice(0, 300) // cap for render performance on very large sheets
    .map((r) => ({ x: r[x_column], y: r[y_column] }))

  if (points.length < 3) return null

  const strength = Math.abs(correlation) > 0.7 ? 'a strong' : Math.abs(correlation) > 0.4 ? 'a moderate' : 'a weak'
  const direction = correlation > 0 ? 'positive' : 'negative'

  return (
    <Card
      title={title}
      description={`${description} The data shows ${strength} ${direction} relationship (correlation: ${correlation}).`}
      badge="Scatter Plot"
    >
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 24 }}>
          <CartesianGrid {...GRID_STYLE} />
          <XAxis
            type="number" dataKey="x" {...AXIS_STYLE}
            label={{ value: x_label, position: 'insideBottom', offset: -16, fill: '#7286A8', fontSize: 11 }}
          />
          <YAxis
            type="number" dataKey="y" {...AXIS_STYLE}
            label={{ value: y_label, angle: -90, position: 'insideLeft', fill: '#7286A8', fontSize: 11, style: { textAnchor: 'middle' } }}
          />
          <ZAxis range={[50, 50]} />
          <Tooltip
            cursor={{ strokeDasharray: '3 3', stroke: '#2A3B5C' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload
              return (
                <div style={{ background: '#0E1525', border: '1px solid #2A3B5C', borderRadius: 10, padding: '10px 14px' }}>
                  <p style={{ color: '#F4F7FF', fontSize: 12.5 }}>{x_label}: <strong>{p.x}</strong></p>
                  <p style={{ color: '#F4F7FF', fontSize: 12.5 }}>{y_label}: <strong>{p.y}</strong></p>
                </div>
              )
            }}
          />
          <Scatter data={points} fill={COLORS[0]} fillOpacity={0.65} />
        </ScatterChart>
      </ResponsiveContainer>
    </Card>
  )
}
