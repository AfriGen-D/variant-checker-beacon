'use client';

import { ReactNode } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';

interface Column<T> {
  header: string;
  accessor: (item: T) => ReactNode;
  className?: string;
}

interface EntityTableProps<T> {
  columns: Column<T>[];
  data: T[] | undefined;
  isLoading: boolean;
  error: Error | null;
  emptyMessage?: string;
  errorMessage?: string;
  onRowClick?: (item: T) => void;
  keyExtractor: (item: T) => string;
}

export function EntityTable<T>({
  columns,
  data,
  isLoading,
  error,
  emptyMessage = 'No data available.',
  errorMessage = 'Failed to load data',
  onRowClick,
  keyExtractor,
}: EntityTableProps<T>) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map(i => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <p className="text-destructive font-semibold mb-2">{errorMessage}</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground py-8">{emptyMessage}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map(col => (
              <TableHead key={col.header} className={col.className}>{col.header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map(item => (
            <TableRow
              key={keyExtractor(item)}
              className={onRowClick ? 'cursor-pointer' : undefined}
              onClick={() => onRowClick?.(item)}
            >
              {columns.map(col => (
                <TableCell key={col.header} className={col.className}>
                  {col.accessor(item)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
