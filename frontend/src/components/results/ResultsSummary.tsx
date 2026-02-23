import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatVariant, formatTimestamp } from '@/lib/utils/formatters';
import type { VariantQuery, BeaconResponse, GenomicVariant } from '@/lib/api/types';

interface ResultsSummaryProps {
  query: VariantQuery;
  response: BeaconResponse<GenomicVariant>;
}

export function ResultsSummary({ query, response }: ResultsSummaryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Query Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <span className="text-sm font-medium text-muted-foreground">Variant:</span>
            <p className="text-sm font-mono">
              {formatVariant(
                query.referenceName,
                query.start || 0,
                query.referenceBases || '',
                query.alternateBases || ''
              )}
            </p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">Assembly:</span>
            <p className="text-sm">{query.assemblyId}</p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">Timestamp:</span>
            <p className="text-sm">{formatTimestamp(response.meta.timestamp)}</p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">Beacon ID:</span>
            <p className="text-sm">{response.meta.beaconId}</p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">API Version:</span>
            <p className="text-sm">{response.meta.apiVersion}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
