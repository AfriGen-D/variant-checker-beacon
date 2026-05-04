/**
 * Format a number with commas for thousands
 * @param num - Number to format
 * @returns Formatted string
 */
export function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Format a genomic position with commas
 * @param position - Genomic position
 * @returns Formatted position string
 */
export function formatPosition(position: number): string {
  return formatNumber(position);
}

/**
 * Format a timestamp to readable date/time
 * @param timestamp - ISO timestamp string
 * @returns Formatted date/time string
 */
export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

/**
 * Format a date to short format
 * @param timestamp - ISO timestamp string
 * @returns Formatted date string
 */
export function formatDate(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleDateString();
}

/**
 * Truncate a string to a maximum length
 * @param str - String to truncate
 * @param maxLength - Maximum length
 * @returns Truncated string
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength) + '...';
}

/**
 * Format variant notation (e.g., "chr1:12345 A>T")
 * @param chr - Chromosome
 * @param pos - Position
 * @param ref - Reference base
 * @param alt - Alternate base
 * @returns Formatted variant string
 */
export function formatVariant(chr: string, pos: number, ref: string, alt: string): string {
  return `chr${chr}:${formatPosition(pos)} ${ref}>${alt}`;
}
