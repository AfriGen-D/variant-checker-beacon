'use client';

import { useQueryStore } from '@/lib/store/queryStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { formatVariant, formatDate } from '@/lib/utils/formatters';

interface QueryHistoryProps {
  onSelectQuery?: (query: any) => void;
}

export function QueryHistory({ onSelectQuery }: QueryHistoryProps) {
  const { queryHistory, clearHistory } = useQueryStore();

  if (queryHistory.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Query History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">No queries yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg">Query History</CardTitle>
          <Button size="sm" variant="outline" onClick={clearHistory}>
            Clear
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {queryHistory.map((item, index) => (
            <div
              key={index}
              className="p-3 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
              onClick={() => onSelectQuery?.(item.query)}
            >
              <div className="flex justify-between items-start mb-1">
                <p className="text-sm font-mono font-medium">
                  {formatVariant(
                    item.query.referenceName,
                    item.query.start || 0,
                    item.query.referenceBases || '',
                    item.query.alternateBases || ''
                  )}
                </p>
                {item.result?.response && (
                  <Badge
                    variant={item.result.response.exists ? 'success' : 'destructive'}
                    size="sm"
                  >
                    {item.result.response.exists ? 'YES' : 'NO'}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{formatDate(item.timestamp)}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
