'use client';

import { ExternalLink } from 'lucide-react';
import type { VariantQuery } from '@/lib/api/types';
import { buildExternalLinks, type ExternalLink as DbLink } from '@/lib/utils/externalLinks';

interface ExternalDbLinksProps {
  query: VariantQuery;
  /** 'inline' = compact button row (results header); 'panel' = labelled groups. */
  variant?: 'inline' | 'panel';
}

function LinkButton({ link }: { link: DbLink }) {
  return (
    <a
      href={link.url}
      target="_blank"
      rel="noopener noreferrer"
      title={link.note}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md border bg-background hover:bg-muted hover:border-primary/30 transition-colors"
    >
      {link.label}
      <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
    </a>
  );
}

/**
 * Turns the Boolean answer into a launchpad: deep links into the major variant
 * resources, computed from coordinates alone (see buildExternalLinks). The
 * Beacon says whether the variant is in the African panels; these carry the
 * user on to frequencies, clinical significance and annotations elsewhere.
 */
export function ExternalDbLinks({ query, variant = 'panel' }: ExternalDbLinksProps) {
  const links = buildExternalLinks(query);
  if (links.length === 0) return null;

  if (variant === 'inline') {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {links.map((link) => <LinkButton key={link.id} link={link} />)}
      </div>
    );
  }

  const african = links.filter((l) => l.group === 'african');
  const global = links.filter((l) => l.group === 'global');

  return (
    <div className="space-y-3">
      {african.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">African resources</p>
          <div className="flex flex-wrap gap-2">
            {african.map((link) => <LinkButton key={link.id} link={link} />)}
          </div>
        </div>
      )}
      {global.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">Look up in public databases</p>
          <div className="flex flex-wrap gap-2">
            {global.map((link) => <LinkButton key={link.id} link={link} />)}
          </div>
        </div>
      )}
    </div>
  );
}
