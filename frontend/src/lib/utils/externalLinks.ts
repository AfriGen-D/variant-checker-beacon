import type { VariantQuery } from '../api/types';

export interface ExternalLink {
  id: string;
  label: string;
  url: string;
  /** Short tooltip explaining the destination. */
  note: string;
  /** Grouping for display: African resources first, then global browsers. */
  group: 'african' | 'global';
}

/** Bare chromosome name ("1", "X"), no "chr" prefix. */
function bareChr(referenceName: string): string {
  return referenceName.startsWith('chr') ? referenceName.slice(3) : referenceName;
}

/** "chr"-prefixed name, as UCSC and some browsers expect. */
function prefixedChr(referenceName: string): string {
  return referenceName.startsWith('chr') ? referenceName : `chr${referenceName}`;
}

/** Whether the query carries both alleles (enables exact-variant deep links). */
function hasAlleles(query: VariantQuery): boolean {
  return Boolean(query.referenceBases && query.alternateBases);
}

const isGrch37 = (assembly?: string) => (assembly ?? '').toUpperCase().includes('37');

/**
 * Build coordinate-based deep links into the major public variant resources.
 *
 * Inputs are 1-based (the form/UI convention shared by dbSNP, Ensembl, gnomAD,
 * UCSC and ClinVar), so no coordinate shift is needed — only the gnomAD/UCSC/
 * Ensembl GRCh37↔GRCh38 hostnames and dataset ids differ by assembly.
 *
 * This turns a Boolean "exists?" answer into a launchpad: the Beacon says
 * whether a variant is present in the African panels, and these links carry the
 * user straight to allele frequencies, clinical significance and annotations
 * that live in the global databases.
 */
export function buildExternalLinks(query: VariantQuery): ExternalLink[] {
  const chr = bareChr(query.referenceName);
  const pos = query.start;
  const ref = query.referenceBases;
  const alt = query.alternateBases;
  const grch37 = isGrch37(query.assemblyId);
  const links: ExternalLink[] = [];

  if (pos === undefined) return links;

  // --- African resources (home team) -----------------------------------
  links.push({
    id: 'agvd',
    label: 'AGVD',
    url: `https://agvd.afrigen-d.org/search/res?type=coordinate&input=${prefixedChr(query.referenceName)}:${pos}&dataset=AGVD_24A_Main&page=1`,
    note: 'African Genome Variation Database',
    group: 'african',
  });
  links.push({
    id: 'agmp',
    label: 'AGMP',
    url: `https://agmp.afrigen-d.org/?search_query=${prefixedChr(query.referenceName)}:${pos}&model_selection=variantagmp`,
    note: 'African Genome Medicine Portal',
    group: 'african',
  });

  // --- Global browsers ---------------------------------------------------
  // gnomAD: exact variant page when alleles are known, otherwise a region view.
  if (hasAlleles(query)) {
    links.push({
      id: 'gnomad',
      label: 'gnomAD',
      url: `https://gnomad.broadinstitute.org/variant/${chr}-${pos}-${ref}-${alt}?dataset=${grch37 ? 'gnomad_r2_1' : 'gnomad_r4'}`,
      note: 'Population allele frequencies',
      group: 'global',
    });
  } else {
    links.push({
      id: 'gnomad',
      label: 'gnomAD',
      url: `https://gnomad.broadinstitute.org/region/${chr}-${pos}-${pos}?dataset=${grch37 ? 'gnomad_r2_1' : 'gnomad_r4'}`,
      note: 'Population allele frequencies (region)',
      group: 'global',
    });
  }

  links.push({
    id: 'ensembl',
    label: 'Ensembl',
    url: `https://${grch37 ? 'grch37.' : ''}ensembl.org/Homo_sapiens/Location/View?r=${chr}:${pos}-${query.end ?? pos}`,
    note: 'Gene & transcript annotations',
    group: 'global',
  });

  links.push({
    id: 'ucsc',
    label: 'UCSC',
    url: `https://genome.ucsc.edu/cgi-bin/hgTracks?db=${grch37 ? 'hg19' : 'hg38'}&position=${prefixedChr(query.referenceName)}:${pos}-${query.end ?? pos}`,
    note: 'UCSC Genome Browser',
    group: 'global',
  });

  links.push({
    id: 'dbsnp',
    label: 'dbSNP',
    url: `https://www.ncbi.nlm.nih.gov/snp/?term=${chr}%5BChromosome%5D+AND+${pos}%5BBase+Position+for+Assembly+${grch37 ? 'GRCh37' : 'GRCh38'}%5D`,
    note: 'NCBI variation records',
    group: 'global',
  });

  links.push({
    id: 'clinvar',
    label: 'ClinVar',
    url: `https://www.ncbi.nlm.nih.gov/clinvar/?term=${chr}%5BChromosome%5D+AND+${pos}%5BBase+Position+for+Assembly+${grch37 ? 'GRCh37' : 'GRCh38'}%5D`,
    note: 'Clinical significance',
    group: 'global',
  });

  return links;
}
