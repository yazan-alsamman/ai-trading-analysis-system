import { z } from 'zod';
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';

export const commentSchema = z.object({
  body: z.string().trim().min(2, 'Write at least 2 characters.').max(500, 'Comments are limited to 500 characters.'),
});

export const POST_MAX = 1000;
export const postSchema = z.object({
  body: z.string().trim().min(10, 'Posts need at least 10 characters.').max(POST_MAX, `Posts are limited to ${POST_MAX} characters.`),
  symbols: z.array(z.enum(INSTRUMENT_SYMBOLS)).max(4, 'Tag up to 4 instruments.'),
});

export type CommentForm = z.infer<typeof commentSchema>;
export type PostForm = z.infer<typeof postSchema>;
