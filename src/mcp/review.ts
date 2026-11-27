import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import type { ImageContent } from '@modelcontextprotocol/sdk/types.js'
import { asRecord } from '../contracts/dynamic.js'

export const reviewSchema = {
  type: 'object',
  required: ['directory'],
  additionalProperties: false,
  properties: {
    directory: { type: 'string', description: 'Absolute review output directory' },
    reference: {
      type: 'string',
      description: 'Absolute local reference path, optional after round one',
    },
    defects: { type: 'array', maxItems: 20, items: { type: 'string' } },
    changes: { type: 'array', maxItems: 20, items: { type: 'string' } },
    verdict: { type: 'string', enum: ['pass', 'fail', 'degraded'] },
  },
}

function notes(value: unknown): string[] {
  if (value === undefined) return []
  if (
    !Array.isArray(value) ||
    value.length > 20 ||
    value.some((x) => typeof x !== 'string' || x.length > 500)
  )
    throw new Error('Use up to 20 review notes of 500 characters each')
  return value
}

export async function startReview(raw: unknown, cameras: unknown) {
  const { directory, reference, defects, changes, verdict, ...extra } = asRecord(raw)
  if (Object.keys(extra).length || typeof directory !== 'string' || !path.isAbsolute(directory))
    throw new Error('review needs an absolute directory and supported review options')
  if (reference !== undefined && (typeof reference !== 'string' || !path.isAbsolute(reference)))
    throw new Error('review.reference must be an absolute file path')
  if (verdict !== undefined && !['pass', 'fail', 'degraded'].includes(String(verdict)))
    throw new Error('review.verdict must be pass, fail or degraded')
  const currentDefects = notes(defects)
  const currentChanges = notes(changes)
  await mkdir(directory, { recursive: true })
  const rounds = (await readdir(directory))
    .filter((entry) => /^round-\d{13}-[a-f0-9-]+$/.test(entry))
    .sort()
  let previous: Record<string, unknown> = {}
  for (const id of rounds.reverse()) {
    try {
      previous = asRecord(
        JSON.parse(await readFile(path.join(directory, id, 'review.json'), 'utf8')),
      )
      break
    } catch (error) {
      if (asRecord(error).code !== 'ENOENT') throw error
    }
  }
  // JSON stringification preserves the call's resolved camera parameters. Key ordering is canonical.
  const cameraKey = createHash('sha256').update(stable(cameras)).digest('hex')
  if (previous.cameraKey && previous.cameraKey !== cameraKey)
    throw new Error(
      'Review camera configuration changed. Use the original cameras or a new review directory.',
    )
  const referencePath = reference ?? previous.reference
  const referenceHash =
    typeof referencePath === 'string'
      ? createHash('sha256')
          .update(await readFile(referencePath))
          .digest('hex')
      : null
  if (previous.referenceHash && previous.referenceHash !== referenceHash)
    throw new Error(
      'Review reference changed. Use the original reference or a new review directory.',
    )
  const previousDefects = notes(previous.defects)
  return {
    directory: path.join(directory, `round-${Date.now()}-${randomUUID()}`),
    cameraKey,
    reference: referencePath ?? null,
    referenceHash,
    defects: currentDefects,
    changes: currentChanges,
    verdict: verdict ?? 'degraded',
    repeatedDefects: currentDefects.filter((item) => previousDefects.includes(item)),
  }
}

function stable(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']'
  if (value !== null && typeof value === 'object')
    return (
      '{' +
      Object.entries(asRecord(value))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => JSON.stringify(k) + ':' + stable(v))
        .join(',') +
      '}'
    )
  return JSON.stringify(value) ?? 'null'
}

export async function finishReview(
  review: Awaited<ReturnType<typeof startReview>>,
  views: Record<string, unknown>[],
  images: { index: number; image: ImageContent }[],
) {
  await mkdir(review.directory)
  const paths = await Promise.all(
    images.map(async ({ index, image }) => {
      const file = path.join(review.directory, `view-${index + 1}.png`)
      await writeFile(file, Buffer.from(image.data, 'base64'), { flag: 'wx' })
      return { index, file }
    }),
  )
  const report = {
    ...review,
    views,
    paths,
    verdict: views.every((view) => view.ok) ? review.verdict : 'degraded',
  }
  const file = path.join(review.directory, 'review.json')
  await writeFile(file, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' })
  return { ...report, file }
}
