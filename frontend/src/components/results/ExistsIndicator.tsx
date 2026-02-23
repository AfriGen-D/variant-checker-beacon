import { Badge } from '@/components/ui/Badge';

interface ExistsIndicatorProps {
  exists: boolean;
}

export function ExistsIndicator({ exists }: ExistsIndicatorProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <Badge variant={exists ? 'success' : 'destructive'} size="lg" className="text-2xl py-3 px-8">
        {exists ? 'YES' : 'NO'}
      </Badge>
      <p className="text-muted-foreground mt-4 text-center">
        {exists
          ? 'Variant exists in the database'
          : 'Variant does not exist in the database'}
      </p>
    </div>
  );
}
