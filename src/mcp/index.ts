#!/usr/bin/env node
import { AsyncLocalStorage } from 'node:async_hooks'
import { randomUUID } from 'node:crypto'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import type { CallToolResult, ImageContent, Tool } from '@modelcontextprotocol/sdk/types.js'
import { PLUGIN_VERSION } from '../constants.js'
import { asRecord } from '../contracts/dynamic.js'
import { ensureBackend, killChildHandle, resolveHttpPort } from '../host/backend/index.js'
import type { HostContext } from '../host/context.js'
import { errorLine } from '../tools/errors.js'
import { registerTools } from '../tools/index.js'
import { finishReview, reviewSchema, startReview } from './review.js'

const port = resolveHttpPort()
const sessionId = 'codex-' + randomUUID()
const tools = new Map<string, ToolDefinition>()
const attachments = new AsyncLocalStorage<{ images: ImageContent[]; bytes: number }>()
const limitBytes = 12 * 1024 * 1024
const pngMagic = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])

const toolHost = {
  effect: (mount: () => unknown) => mount(),
  tools: {
    register: (tool: ToolDefinition) => tools.set(tool.name, tool),
    guard: () => undefined,
  },
  get: (name: string) =>
    name === 'attachments'
      ? {
          imageLimits: { mediaTypes: ['image/png'] },
          async saveImage(input: { data: Uint8Array; name: string; mediaType: string }) {
            const store = attachments.getStore()
            const data = Buffer.from(input.data)
            if (!store || data.length < 24 || !data.subarray(0, 8).equals(pngMagic))
              throw new Error('Expected a PNG in the active MCP call')
            if (store.images.length >= 6 || store.bytes + data.length > limitBytes)
              throw new Error('MCP image budget exceeded. Ask for fewer or smaller views.')
            const attachmentId = randomUUID()
            store.bytes += data.length
            store.images.push({
              type: 'image',
              mimeType: input.mediaType,
              data: data.toString('base64'),
            })
            return {
              attachmentId,
              mediaType: input.mediaType,
              bytes: data.length,
              name: input.name,
              width: data.readUInt32BE(16),
              height: data.readUInt32BE(20),
            }
          },
        }
      : undefined,
}
// Register through the existing host surface. Only these three host services are used by the tools.
registerTools(toolHost as unknown as HostContext, port)

const server = new Server(
  { name: 'blend-asset-forge', version: PLUGIN_VERSION },
  {
    capabilities: { tools: {} },
    instructions:
      'Use blender_session doctor then attach to a connected Blender. Use blender_op catalog to discover operations. For multi-angle review call blender_see with views. Use blender_run submit/wait/collect for long jobs.',
  },
)

const listed = [...tools.values()].map(({ name, description, parameters }): Tool => {
  if (name !== 'blender_see')
    return { name, description, inputSchema: parameters as Tool['inputSchema'] }
  const properties = asRecord(asRecord(parameters).properties)
  const frameProperties = { ...properties }
  delete frameProperties.mode
  return {
    name,
    description:
      description +
      ' MCP: pass views (1–6 frame specs) to return labeled PNGs from multiple viewpoints.',
    inputSchema: {
      ...parameters,
      type: 'object',
      properties: {
        ...properties,
        review: reviewSchema,
        views: {
          type: 'array',
          minItems: 1,
          maxItems: 6,
          items: {
            type: 'object',
            properties: { ...frameProperties, label: { type: 'string' } },
            additionalProperties: false,
          },
        },
      },
    },
  }
})

type ToolExec = Parameters<ToolDefinition['execute']>[1]

function errorResult(message: string): CallToolResult {
  return { content: [{ type: 'text', text: message }], isError: true }
}

async function invoke(
  tool: ToolDefinition,
  args: Record<string, unknown>,
  exec: ToolExec,
): Promise<CallToolResult> {
  return attachments.run({ images: [], bytes: 0 }, async () => {
    const value = asRecord(await tool.execute(args, exec))
    const images = attachments.getStore()?.images ?? []
    const failed =
      value.ok === false ||
      asRecord(value.envelope).ok === false ||
      !!asRecord(value.envelope).error
    return {
      content: [
        { type: 'text', text: typeof value.text === 'string' ? value.text : JSON.stringify(value) },
        ...images,
      ],
      structuredContent: value,
      ...(failed ? { isError: true } : {}),
    }
  })
}

async function multiView(
  tool: ToolDefinition,
  args: Record<string, unknown>,
  exec: ToolExec,
): Promise<CallToolResult> {
  const { views, review, ...defaults } = args
  if (!Array.isArray(views) || views.length < 1 || views.length > 6 || 'mode' in defaults)
    return errorResult('views must contain 1–6 frame specifications; omit mode when using views.')
  for (const view of views) {
    if (
      !view ||
      typeof view !== 'object' ||
      Array.isArray(view) ||
      'mode' in view ||
      'views' in view
    )
      return errorResult('Each view must be a single frame specification with an optional label.')
    const { label } = asRecord(view)
    if (label !== undefined && (typeof label !== 'string' || label.length > 120))
      return errorResult('View labels must be strings of at most 120 characters.')
  }
  const content: CallToolResult['content'] = []
  const receipts: Record<string, unknown>[] = []
  const images: { index: number; image: ImageContent }[] = []
  if (
    review !== undefined &&
    !views.every((view) => {
      const spec = { ...defaults, ...asRecord(view) }
      return (
        spec.viewpoint === 'custom' &&
        typeof spec.from === 'string' &&
        typeof spec.look_at === 'string'
      )
    })
  )
    return errorResult(
      'Archived reviews require custom viewpoints with fixed from and look_at coordinates.',
    )
  const archive = review === undefined ? undefined : await startReview(review, { defaults, views })
  let failed = false
  let bytes = 0
  for (const [index, view] of views.entries()) {
    exec.signal.throwIfAborted()
    const { label, ...spec } = asRecord(view)
    const name = typeof label === 'string' && label ? label : `View ${index + 1}`
    const frame = await invoke(tool, { ...defaults, ...spec, mode: 'frame', force: true }, exec)
    const image = frame.content.find((item): item is ImageContent => item.type === 'image')
    bytes += image?.data.length ?? 0
    const ok = !!image && !frame.isError && bytes <= limitBytes
    if (image && ok && archive) images.push({ index, image })
    failed ||= !ok
    content.push({
      type: 'text',
      text: `${name}${image && !ok ? ' · MCP image budget exceeded' : ''}`,
    })
    content.push(...frame.content.filter((item) => item.type !== 'image' || ok))
    receipts.push({ ...frame.structuredContent, label: name, ok })
  }
  const saved = archive ? await finishReview(archive, receipts, images) : undefined
  if (saved)
    content.push({
      type: 'text',
      text:
        'Review saved: ' +
        saved.file +
        (saved.repeatedDefects.length
          ? '\nRepeated defects: ' + saved.repeatedDefects.join(' · ')
          : ''),
    })
  return {
    content,
    structuredContent: { views: receipts, ...(saved ? { review: saved } : {}) },
    ...(failed ? { isError: true } : {}),
  }
}

let backend: Promise<boolean> | undefined
server.setRequestHandler(ListToolsRequestSchema, () => ({ tools: listed }))
server.setRequestHandler(CallToolRequestSchema, async ({ params }, extra) => {
  const tool = tools.get(params.name)
  if (!tool) return errorResult(`Unknown tool: ${params.name}`)
  const args = params.arguments ?? {}
  const exec = {
    signal: extra.signal,
    callId: String(extra.requestId),
    agent: { id: sessionId, role: 'main', session: { id: sessionId }, displayName: 'Codex' },
  } as unknown as ToolExec
  try {
    if (
      params.name === 'blender_see' &&
      'views' in args &&
      (!Array.isArray(args.views) || !args.views.length)
    )
      return errorResult('views must contain 1–6 frame specifications.')
    const catalog =
      (params.name === 'blender_op' && ['catalog', 'help'].includes(String(args.op))) ||
      (params.name === 'blender_run' &&
        ['asset_catalog', 'asset_provider'].includes(String(args.action)))
    if (!catalog) {
      backend ??= ensureBackend(port).finally(() => {
        backend = undefined
      })
      if (!(await backend))
        return errorResult(
          `Blender Gateway is unavailable on 127.0.0.1:${port}. Check the Gateway log.`,
        )
    }
    extra.signal.throwIfAborted()
    if (params.name === 'blender_see' && 'review' in args && !('views' in args))
      return errorResult('review must be used with the multi-view capture array.')
    if (params.name === 'blender_see' && 'views' in args) return await multiView(tool, args, exec)
    return await invoke(tool, args, exec)
  } catch (error) {
    return errorResult(errorLine(error))
  }
})

server.onclose = () => {
  killChildHandle()
}
process.once('SIGINT', () => void server.close())
process.once('SIGTERM', () => void server.close())
await server.connect(new StdioServerTransport())
