import { Skeleton } from '@/components/ui/Skeleton';

export default function Loading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <Skeleton className="h-12 w-12 rounded-full mx-auto" />
        <Skeleton className="h-4 w-24 mx-auto" />
      </div>
    </div>
  );
}
