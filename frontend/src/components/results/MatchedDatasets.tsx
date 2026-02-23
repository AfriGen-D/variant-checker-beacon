import { Badge } from '@/components/ui/Badge';
import type { DatasetAlleleResponse } from '@/lib/api/types';

interface MatchedDatasetsProps {
  datasetResponses: DatasetAlleleResponse[];
}

export function MatchedDatasets({ datasetResponses }: MatchedDatasetsProps) {
  const matched = datasetResponses.filter(d => d.exists);
  const notMatched = datasetResponses.filter(d => !d.exists);

  if (datasetResponses.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-muted-foreground">
        Matched {matched.length} of {datasetResponses.length} dataset{datasetResponses.length !== 1 ? 's' : ''}
      </p>
      <div className="flex flex-wrap gap-2">
        {matched.map(d => (
          <Badge key={d.datasetId} variant="success" size="sm" title={d.datasetId}>
            {d.datasetName}
          </Badge>
        ))}
        {notMatched.map(d => (
          <Badge key={d.datasetId} variant="outline" size="sm" className="opacity-60" title={d.datasetId}>
            {d.datasetName}
          </Badge>
        ))}
      </div>
    </div>
  );
}
