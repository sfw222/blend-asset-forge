import { once } from 'node:events'
import type { AddressInfo } from 'node:net'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import { describe, expect, it } from 'vitest'
import { createGatewayApp } from '../../runtime/gateway/app.js'

describe('Codex stdio MCP', () => {
  it('lists the six shared tools and serves the catalog without Blender', async () => {
    const gateway = createGatewayApp({ port: 0 })
    gateway.server.listen(0, '127.0.0.1')
    await once(gateway.server, 'listening')
    const { port } = gateway.server.address() as AddressInfo
    const transport = new StdioClientTransport({
      command: process.execPath,
      args: ['lib/mcp/index.js'],
      cwd: process.cwd(),
      env: { DSH_BLENDER_GATEWAY_PORT: String(port), DSH_BLENDER_TEST_NO_SPAWN: '1' },
      stderr: 'pipe',
    })
    const client = new Client({ name: 'codex-smoke', version: '1' })
    try {
      await client.connect(transport)
      const { tools } = await client.listTools()
      expect(tools.map(({ name }) => name)).toEqual([
        'blender_session',
        'blender_op',
        'blender_py',
        'blender_see',
        'blender_run',
        'blender_inspect',
      ])
      expect(tools[3].inputSchema.properties).toHaveProperty('views')
      expect(tools[4].inputSchema.properties).toHaveProperty(
        'asset_recipe.description',
        expect.stringContaining('作业模板'),
      )
      expect(tools[1].description).toContain('预设库')
      const catalog = await client.callTool({ name: 'blender_op', arguments: { op: 'catalog' } })
      expect(catalog.isError).not.toBe(true)
      expect(JSON.stringify(catalog)).toContain('visualreport')
      const invalid = await client.callTool({ name: 'blender_see', arguments: { views: [] } })
      expect(invalid.isError).toBe(true)
    } finally {
      await client.close()
      gateway.close()
    }
  })
})
