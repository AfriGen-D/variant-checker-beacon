'use client';

import { useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { useQueryStore, type QueryHistoryItem } from '@/lib/store/queryStore';

export function QueryActivityChart() {
  const { queryHistory } = useQueryStore();

  const chartData = useMemo(() => {
    if (queryHistory.length === 0) return [];

    const grouped: Record<string, { total: number; found: number }> = {};
    queryHistory.forEach((item: QueryHistoryItem) => {
      const date = new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      if (!grouped[date]) grouped[date] = { total: 0, found: 0 };
      grouped[date].total++;
      if (item.result?.response?.exists) grouped[date].found++;
    });

    return Object.entries(grouped)
      .map(([date, counts]) => ({ date, ...counts }))
      .reverse();
  }, [queryHistory]);

  if (chartData.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Query Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.15}
                name="Total Queries"
              />
              <Area
                type="monotone"
                dataKey="found"
                stroke="hsl(var(--success))"
                fill="hsl(var(--success))"
                fillOpacity={0.15}
                name="Found"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
