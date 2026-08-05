'use client';

import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { Dataset } from '@/lib/api/types';

type Metric = 'variants' | 'samples';

interface ChromosomeDistributionProps {
  datasets: Dataset[];
}

export function ChromosomeDistribution({ datasets }: ChromosomeDistributionProps) {
  const [metric, setMetric] = useState<Metric>('variants');

  const chartData = datasets
    .map(d => ({
      name: d.name.length > 15 ? d.name.slice(0, 15) + '...' : d.name,
      fullName: d.name,
      variants: d.variantCount ?? 0,
      samples: d.sampleCount ?? 0,
    }))
    .filter(d => d[metric] > 0);

  if (chartData.length === 0) return null;

  const title = metric === 'variants' ? 'Variant Distribution by Dataset' : 'Sample Distribution by Dataset';
  const axisLabel = metric === 'variants' ? 'Variants' : 'Samples';

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-lg">{title}</CardTitle>
        <div className="flex gap-1 rounded-md border p-0.5">
          <Button
            variant={metric === 'variants' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setMetric('variants')}
            aria-pressed={metric === 'variants'}
          >
            Variants
          </Button>
          <Button
            variant={metric === 'samples' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setMetric('samples')}
            aria-pressed={metric === 'samples'}
          >
            Samples
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="name" className="text-xs" tick={{ fontSize: 12 }} />
              <YAxis
                className="text-xs"
                tick={{ fontSize: 12 }}
                label={{ value: axisLabel, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 12 } }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--background)',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                formatter={(value) => [
                  typeof value === 'number' ? value.toLocaleString() : String(value ?? ''),
                  axisLabel,
                ]}
                labelFormatter={(label, payload) =>
                  payload?.[0]?.payload?.fullName ?? label
                }
              />
              <Bar dataKey={metric} fill="#94a3b8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
