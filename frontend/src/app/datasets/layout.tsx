import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Datasets | Beacon v2',
  description: 'Browse genomic datasets available for variant discovery queries.',
};

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
