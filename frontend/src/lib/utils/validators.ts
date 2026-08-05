import { z } from 'zod';
import {
  MAX_GENOMIC_POSITION,
  MIN_GENOMIC_POSITION,
  MAX_REGION_SPAN,
  BASES,
  CHROMOSOMES,
} from './constants';

// Valid chromosome values
const validChromosomes = CHROMOSOMES.map((c) => c.value);

// Valid base values
const validBases = BASES.join('');

// Shared field builders so variant and region modes validate coordinates the
// same way (the only difference between modes is which fields are required).
const assemblyField = z.string().min(1, 'Assembly is required');
const chromosomeField = z.string().refine((val) => validChromosomes.includes(val as any), {
  message: 'Invalid chromosome. Must be 1-22, X, Y, or MT',
});
const positionField = (label: string) =>
  z.coerce
    .number({
      required_error: `${label} is required`,
      invalid_type_error: `${label} must be a number`,
    })
    .int(`${label} must be an integer`)
    .min(MIN_GENOMIC_POSITION, `${label} must be >= ${MIN_GENOMIC_POSITION}`)
    .max(MAX_GENOMIC_POSITION, `${label} must be <= ${MAX_GENOMIC_POSITION.toLocaleString()}`);

/**
 * Zod schema for variant query form
 */
export const variantQuerySchema = z.object({
  assemblyId: z.string().min(1, 'Assembly is required'),
  referenceName: z.string().refine((val) => validChromosomes.includes(val as any), {
    message: 'Invalid chromosome. Must be 1-22, X, Y, or MT',
  }),
  start: z.coerce
    .number({
      required_error: 'Start position is required',
      invalid_type_error: 'Start position must be a number',
    })
    .int('Start position must be an integer')
    .min(MIN_GENOMIC_POSITION, `Start position must be >= ${MIN_GENOMIC_POSITION}`)
    .max(MAX_GENOMIC_POSITION, `Start position must be <= ${MAX_GENOMIC_POSITION.toLocaleString()}`),
  end: z.preprocess(
    (val) => (val === '' || val === undefined || val === null ? undefined : val),
    z.coerce
      .number({ invalid_type_error: 'End position must be a number' })
      .int('End position must be an integer')
      .min(MIN_GENOMIC_POSITION)
      .max(MAX_GENOMIC_POSITION)
      .optional(),
  ),
  referenceBases: z
    .string()
    .min(1, 'Reference base is required')
    .regex(new RegExp(`^[${validBases}]+$`), {
      message: `Reference bases must contain only ${validBases}`,
    })
    .transform((val) => val.toUpperCase()),
  alternateBases: z
    .string()
    .min(1, 'Alternate base is required')
    .regex(new RegExp(`^[${validBases}]+$`), {
      message: `Alternate bases must contain only ${validBases}`,
    })
    .transform((val) => val.toUpperCase()),
}).refine(
  (data) => {
    // Validate end >= start if end is provided
    if (data.end !== undefined) {
      return data.end >= data.start;
    }
    return true;
  },
  {
    message: 'End position must be greater than or equal to start position',
    path: ['end'],
  }
);

export type VariantQueryFormData = z.infer<typeof variantQuerySchema>;

/**
 * Zod schema for the Region (range) query form. Both start and end are
 * required and there are no allele fields — the backend returns every variant
 * overlapping [start, end] (capped at 10M bases).
 */
export const regionQuerySchema = z
  .object({
    assemblyId: assemblyField,
    referenceName: chromosomeField,
    start: positionField('Start position'),
    end: positionField('End position'),
  })
  .refine((data) => data.end >= data.start, {
    message: 'End position must be greater than or equal to start position',
    path: ['end'],
  })
  // The API receives start - 1, so the range the backend measures against
  // MAX_RANGE is end - (start - 1) — the inclusive base count of the region.
  .refine((data) => data.end - data.start + 1 <= MAX_REGION_SPAN, {
    message: `Region must be ${MAX_REGION_SPAN.toLocaleString()} bases or fewer`,
    path: ['end'],
  });

export type RegionQueryFormData = z.infer<typeof regionQuerySchema>;
