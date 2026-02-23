'use client';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import type { Dataset } from '@/lib/api/types';

interface ChromosomeDistributionProps {
  datasets: Dataset[];
}

export function ChromosomeDistribution({ datasets }: ChromosomeDistributionProps) {
  const chartData = datasets
    .filter(d => d.variantCount !== undefined && d.variantCount > 0)
    .map(d => ({
      name: d.name.length > 15 ? d.name.slice(0, 15) + '...' : d.name,
      fullName: d.name,
      variants: d.variantCount ?? 0,
    }));

  if (chartData.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Variant Distribution by Dataset</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="name" className="text-xs" tick={{ fontSize: 12 }} />
              <YAxis className="text-xs" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                formatter={(value: number) => [value.toLocaleString(), 'Variants']}
                labelFormatter={(label: string, payload) =>
                  payload?.[0]?.payload?.fullName ?? label
                }
              />
              <Bar dataKey="variants" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
