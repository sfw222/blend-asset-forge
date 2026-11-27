import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { runBatch } from '../../runtime/ext/fal/fal-batch.mjs'

const [, , image, realGlb, destination] = process.argv
assert(
  image && realGlb && destination,
  'Pass a local PNG, a Blender-exported GLB and a new output directory.',
)
const dir = path.resolve(destination)
await mkdir(dir)
const manifest = path.join(dir, 'manifest.json')
const output = path.join(dir, 'from-provider.glb')
const createJob = (id) => ({
  id,
  image: path.resolve(image),
  endpoint: 'fal-ai/trellis',
  output: path.basename(output),
})
await writeFile(manifest, JSON.stringify({ jobs: [createJob('scene')] }))
assert.equal((await runBatch('check', manifest, { key: '' }))[0].state, 'ready')

let submissions = 0
const glb = await readFile(realGlb)
const enqueue = 'https://queue.fal.run/fal-ai/trellis'
const opts = {
  key: 'fixture-key',
  async fetchFn(url, request) {
    if (url === enqueue) {
      submissions++
      assert(JSON.parse(request.body).image_url.startsWith('data:image/png;base64,'))
      return Response.json({
        request_id: 'fixture-01',
        status_url: enqueue + '/requests/fixture-01/status',
        response_url: enqueue + '/requests/fixture-01',
      })
    }
    if (url.endsWith('/status')) return Response.json({ status: 'COMPLETED' })
    if (url.endsWith('/fixture-01'))
      return Response.json({
        model_urls: { glb: { url: 'https://assets.example.test/model.glb' } },
      })
    assert.equal(url, 'https://assets.example.test/model.glb')
    assert.equal(
      request.headers,
      undefined,
      'The download must not inherit the provider credential',
    )
    return new Response(glb)
  },
}
assert.equal((await runBatch('submit', manifest, opts))[0].request_id, 'fixture-01')
await runBatch('submit', manifest, opts)
assert.equal(submissions, 1)
assert.equal((await runBatch('collect', manifest, opts))[0].state, 'downloaded')
assert.deepEqual(await readFile(output), glb)

const uncertain = path.join(dir, 'uncertain.json')
await writeFile(uncertain, JSON.stringify({ jobs: [createJob('uncertain')] }))
let attempts = 0
const interrupted = {
  key: 'fixture-key',
  async fetchFn() {
    attempts++
    throw new Error('connection reset after request')
  },
}
assert.equal((await runBatch('submit', uncertain, interrupted))[0].state, 'submission-uncertain')
await runBatch('submit', uncertain, interrupted)
assert.equal(attempts, 1)

const exe = process.env.DSH_BLENDER_EXE
assert(exe, 'Set DSH_BLENDER_EXE for the Blender reimport.')
const code = `import bpy; assert bpy.ops.import_scene.gltf(filepath=${JSON.stringify(output)}) == {'FINISHED'}; assert any(o.type=='MESH' and o.name!='Cube' for o in bpy.context.scene.objects)`
await promisify(execFile)(exe, [
  '-b',
  '--factory-startup',
  '--python-exit-code',
  '1',
  '--python-expr',
  code,
])
await writeFile(
  path.join(dir, 'provider-proof.json'),
  JSON.stringify(
    {
      transport: 'mocked',
      submissions,
      uncertainAttempts: attempts,
      importedInBlender: true,
      liveProviderRequests: 0,
    },
    null,
    2,
  ),
)
console.log(
  'PASS: Fal offline validation, submit/collect, duplicate prevention, and Blender GLB reimport.',
)
