import assert from 'node:assert/strict'
import { execFile, spawn } from 'node:child_process'
import { once } from 'node:events'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import { promisify } from 'node:util'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

const root = path.resolve(import.meta.dirname, '../..')
const supplied = process.argv[2]
assert(
  supplied,
  'Pass a directory containing reference.png; outputs go to a fresh run-* subdirectory.',
)
const base = path.resolve(supplied)
const reference = path.join(base, 'reference.png')
assert(
  (await readFile(reference)).subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
)
const work = path.join(base, `run-${Date.now()}`)
await mkdir(work)
console.log(`Chair evidence: ${work}`)

const exe = process.env.DSH_BLENDER_EXE
assert(exe, 'Set DSH_BLENDER_EXE to the Blender executable.')
const tempServer = net.createServer().listen(0, '127.0.0.1')
await once(tempServer, 'listening')
const port = tempServer.address().port
await new Promise((resolve) => tempServer.close(resolve))
const env = Object.fromEntries(
  Object.entries(process.env).filter(([, value]) => value !== undefined),
)
const mcpEnv = {
  ...env,
  DSH_BLENDER_WORKDIR: work,
  DSH_BLENDER_GATEWAY_PORT: String(port),
  DSH_BLENDER_TEST_NO_SPAWN: '0',
}
const blenderEnv = {
  ...mcpEnv,
  DSHBB_GATEWAY_PORT: String(port),
  BLENDER_USER_SCRIPTS: path.join(work, 'user_scripts'),
  BLENDER_USER_EXTENSIONS: path.join(work, 'user_extensions'),
  BLENDER_USER_CONFIG: path.join(work, 'user_config'),
  PYTHONDONTWRITEBYTECODE: '1',
  PYTHONIOENCODING: 'utf-8',
}
const runExe = promisify(execFile)
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [path.join(root, 'lib/mcp/index.js')],
  cwd: root,
  env: mcpEnv,
  stderr: 'pipe',
})
const client = new Client({ name: 'codex-chair-test', version: '1' })
const scripts = path.join(root, 'tests', 'e2e', 'blender')
const fixture = await readFile(path.join(scripts, 'codex_chair_scene.py'), 'utf8')
const proof = {}
const expanded = process.argv.includes('--full')
let blender
let blenderLog = ''

async function tool(name, args) {
  const result = await client.callTool({ name: 'blender_' + name, arguments: args }, undefined, {
    timeout: 360000,
  })
  assert.equal(result.isError, undefined, `${name}: ${JSON.stringify(result).slice(0, 1800)}`)
  return result
}

function literal(value) {
  return JSON.stringify(value)
}

const viewSpecs = [
  {
    label: 'front three-quarter',
    viewpoint: 'custom',
    from: '-1.02,-2.37,1.17',
    look_at: '0,0,0.446',
  },
  { label: 'front', viewpoint: 'custom', from: '0,-2.5,0.446', look_at: '0,0,0.446' },
  { label: 'side', viewpoint: 'custom', from: '-2.5,0,0.446', look_at: '0,0,0.446' },
]

async function capture(pass) {
  const result = await tool('see', {
    aspect: '1:1',
    max_size: 544,
    shading: 'SOLID',
    overlays: false,
    ortho: true,
    ortho_scale: 1.07,
    views: viewSpecs,
    ...(expanded
      ? {
          review: {
            directory: path.join(work, 'review-rounds'),
            reference,
            defects: ['check backrest framing'],
            changes: [pass],
          },
        }
      : {}),
  })
  const images = result.content.filter((block) => block.type === 'image')
  assert.equal(images.length, 3)
  assert.equal(new Set(images.map((image) => image.data)).size, 3, 'All three views must differ')
  assert(result.structuredContent.views.every((view) => view.ok === true))
  if (expanded) {
    const review = result.structuredContent.review
    assert.equal(review.paths.length, 3)
    assert.deepEqual(review.repeatedDefects, pass === 'refined' ? ['check backrest framing'] : [])
    proof[pass + 'Review'] = review.file
  }
  await Promise.all(
    images.map((image, index) =>
      writeFile(path.join(work, `${pass}-${index}.png`), Buffer.from(image.data, 'base64')),
    ),
  )
  console.log(`${pass}: ${images.length} MCP PNGs`)
}

async function recipe(file, assetRecipe, options) {
  const job = await tool('run', {
    action: 'submit',
    kind: 'headless',
    file,
    outdir: work,
    asset_recipe: assetRecipe,
    asset_options: options,
  })
  const id = job.structuredContent.job.id
  console.log(`${assetRecipe} submitted: ${id}`)
  await tool('run', { action: 'wait', id, timeout_ms: 240000 })
  const collected = await tool('run', { action: 'collect', id, tail: 8000 })
  return { id, job: collected.structuredContent.job, text: collected.content[0].text }
}

async function expandedChecks(scene, low, rigScene) {
  const catalog = await tool('run', { action: 'asset_catalog' })
  assert.equal(Object.keys(catalog.structuredContent.recipes).length, 39)
  const density = await recipe(scene, 'texel_density', {
    objects: [low],
    res: 512,
    save_blend: false,
  })
  assert.equal(density.job.state, 'completed', density.text)
  const densityReport = JSON.parse(
    await readFile(path.join(work, density.id, 'asset-report.json'), 'utf8'),
  )
  assert(densityReport.result.objects[low].px_per_m > 0)
  const risk = await recipe(scene, 'review_shots', {
    objects: [low],
    views: ['front', 'right'],
    res: 256,
  })
  assert.equal(risk.job.state, 'completed', risk.text)
  assert((await readFile(path.join(work, risk.id, 'review.png'))).length > 500)
  const blockedPath = await recipe(scene, 'review_shots', { objects: [low], out: '../escape.png' })
  assert.equal(blockedPath.job.state, 'failed', blockedPath.text)
  assert.match(blockedPath.text, /Recipe outputs must remain in the job directory/)
  const batch = await recipe(undefined, 'batch_process', {
    inp: [scene, rigScene],
    op: 'convert',
    to: 'glb',
  })
  assert.equal(batch.job.state, 'completed', batch.text)
  const batchReport = JSON.parse(
    await readFile(path.join(work, batch.id, 'asset-report.json'), 'utf8'),
  )
  assert.equal(batchReport.result.files, 2)
  for (const output of batchReport.result.results) {
    assert.equal((await readFile(output.out)).toString('ascii', 0, 4), 'glTF')
  }
  const manifest = path.join(work, 'fal-preflight.json')
  await writeFile(
    manifest,
    JSON.stringify({
      jobs: [
        {
          id: 'probe',
          endpoint: 'fal-ai/trellis',
          image: reference,
          output: 'fal/probe.glb',
          input: { texture_size: 512 },
        },
      ],
    }),
  )
  const provider = await tool('run', { action: 'asset_provider', op: 'check', file: manifest })
  assert.equal(provider.structuredContent.jobs[0].state, 'ready')
  const refused = await client.callTool({
    name: 'blender_run',
    arguments: { action: 'asset_provider', op: 'submit', file: manifest },
  })
  assert.equal(refused.isError, true)
  assert.match(refused.content[0].text, /allow_upload/)
  proof.expanded = {
    density: density.id,
    contactSheet: risk.id,
    blockedPath: blockedPath.id,
    batch: batch.id,
    provider: 'offline preflight and upload refusal',
  }
  if (process.env.BLENDER_ACCEPTANCE_FOOTAGE) {
    const tracked = await recipe(undefined, 'track_camera', {
      clip: process.env.BLENDER_ACCEPTANCE_FOOTAGE,
      focal: 35,
      sensor: 36,
    })
    assert.equal(tracked.job.state, 'completed', tracked.text)
    const trackedReport = JSON.parse(
      await readFile(path.join(work, tracked.id, 'asset-report.json'), 'utf8'),
    )
    assert.equal(trackedReport.result.solved, true)
    assert(trackedReport.result.solve_error_px < 0.5)
    proof.expanded.tracking = trackedReport
  }
}

try {
  await client.connect(transport)
  transport.stderr?.on('data', (chunk) => process.stderr.write(chunk))
  assert.equal((await client.listTools()).tools.length, 6)
  await tool('session', { action: 'status' })
  await runExe(
    exe,
    [
      '--command',
      'extension',
      'install-file',
      '-r',
      'user_default',
      '-e',
      path.join(root, 'extension/dsh_blender_bridge.zip'),
    ],
    { env: blenderEnv },
  )
  const start =
    'import bpy, addon_utils; addon_utils.enable("bl_ext.user_default.dsh_blender_bridge", persistent=True); bpy.ops.dshbb.start_server()'
  blender = spawn(exe, ['--factory-startup', '--python-exit-code', '1', '--python-expr', start], {
    env: blenderEnv,
    cwd: root,
    windowsHide: true,
  })
  blender.stdout.on('data', (buffer) => {
    blenderLog += buffer
  })
  blender.stderr.on('data', (buffer) => {
    blenderLog += buffer
  })
  const deadline = Date.now() + 45000
  while (true) {
    assert.equal(blender.exitCode, null, blenderLog)
    const response = await fetch(`http://127.0.0.1:${port}/doctor`)
    if ((await response.json()).addon?.kind === 'ok') break
    assert(Date.now() < deadline, `Blender addon handshake timed out\n${blenderLog}`)
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  const doctor = await tool('session', { action: 'doctor' })
  assert.equal(doctor.structuredContent.kind, 'ok')
  proof.doctor = doctor.structuredContent
  await tool('session', { action: 'attach' })
  console.log('doctor kind=ok; GUI attached')

  const digest = await tool('op', {
    op: 'img_digest',
    args: { path: reference },
    attach_images: false,
  })
  proof.reference = digest.structuredContent
  await tool('py', { code: `${fixture}\nbuild_chair(False)`, see: false })
  await capture('blockout')
  const review = {
    source: 'reference.png',
    observations: [
      'The blockout seat rim is thicker than the reference.',
      'The reference has a taller panel and slimmer legs.',
    ],
    changes: ['Seat 46 → 25 mm', 'Panel 110 → 163 mm and raised 31 mm', 'Legs 55 → 43 mm'],
  }
  await writeFile(path.join(work, 'visual-review.json'), JSON.stringify(review, null, 2))
  await tool('py', { code: `${fixture}\nbuild_chair(True)`, see: false })
  await capture('refined')
  assert.notDeepEqual(
    await readFile(path.join(work, 'blockout-0.png')),
    await readFile(path.join(work, 'refined-0.png')),
  )
  const low = 'SM_OakChair'
  await tool('op', { op: 'uv_smart_project', args: { objects: [low], island_margin: 0.02 } })
  const gate = await tool('op', { op: 'gate_run', args: { preset: 'delivery' } })
  assert.equal(gate.structuredContent.envelope.verdict, 'pass', gate.content[0].text)
  proof.gate = gate.structuredContent

  const scene = path.join(work, 'chair-source.blend')
  await tool('py', { code: `bpy.ops.wm.save_as_mainfile(filepath=${literal(scene)})`, see: false })
  const original = await readFile(scene)
  const collision = Array.from({ length: 6 }, (_, index) => `UCX_${low}_0${index}`)
  const {
    id,
    job,
    text: jobText,
  } = await recipe(scene, 'prepare_unreal', {
    low,
    bake: { high: ['OakChair_High'], res: 512, samples: 12, extrusion: 0.006 },
    lod: { ratios: [0.52, 0.29] },
    unreal: { collision },
  })
  assert.equal(job.state, 'completed', jobText)
  const report = JSON.parse(await readFile(path.join(work, id, 'asset-report.json'), 'utf8'))
  assert.deepEqual(
    await readFile(scene),
    original,
    'Preparation must preserve the original Blend file',
  )
  assert.deepEqual(report.unreal.collision, collision)
  assert.equal(report.lods.length, 3)
  assert(
    report.lods[0].triangles > report.lods[1].triangles &&
      report.lods[1].triangles > report.lods[2].triangles,
  )
  assert.equal(Object.keys(report.textures.maps).length, 6)
  proof.asset = report

  const renderPath = path.join(work, 'chair-render.png')
  const validation = path.join(work, 'fbx-roundtrip.json')
  const verify = path.join(work, 'verify.py')
  await writeFile(
    verify,
    `${fixture}\nimport json\n` +
      `assert sum(bool(image.packed_file) for image in bpy.data.images) >= 5\nbeauty(${literal(renderPath)})\n` +
      `files = json.loads(${literal(JSON.stringify([report.unreal.base, ...report.unreal.lods.map((lod) => lod.file)]))})\n` +
      `checks=[]\nfor file in files:\n    for obj in list(bpy.context.scene.objects):\n        bpy.data.objects.remove(obj, do_unlink=True)\n` +
      `    assert bpy.ops.import_scene.fbx(filepath=file) == {'FINISHED'}\n` +
      `    objects=[o for o in bpy.context.scene.objects if o.type == 'MESH']\n` +
      `    ob=next(o for o in objects if o.name.startswith(${literal(low)}))\n` +
      `    checks.append({'file':file,'mesh_names':[o.name for o in objects], 'tris':sum(len(p.vertices)-2 for p in ob.data.polygons), 'dimensions':list(ob.dimensions)})\n` +
      `with open(${literal(validation)},'w',encoding='utf8') as output:\n    json.dump(checks,output,indent=2)\n`,
  )
  await runExe(
    exe,
    ['-b', '--factory-startup', report.blend, '--python-exit-code', '1', '--python', verify],
    { env: blenderEnv, maxBuffer: 4 * 1024 * 1024 },
  )
  const roundtrip = JSON.parse(await readFile(validation, 'utf8'))
  assert.deepEqual(
    roundtrip.map((entry) => entry.tris),
    report.lods.map((lod) => lod.triangles),
  )
  assert.deepEqual(roundtrip[0].mesh_names.sort(), [low, ...collision].sort())
  assert.deepEqual(
    roundtrip.slice(1).map((entry) => entry.mesh_names),
    [[`${low}_LOD1`], [`${low}_LOD2`]],
  )
  assert(
    roundtrip[0].dimensions.every(
      (value, index) => Math.abs(value - report.unreal.bounds_m[index]) < 0.002,
    ),
  )
  proof.roundtrip = roundtrip

  const conflict = path.join(work, 'hand-authored-lod.blend')
  await tool('py', {
    code: `src=bpy.data.objects[${literal(low)}]\nob=bpy.data.objects.new(${literal(low + '_LOD1')}, src.data)\nbpy.context.collection.objects.link(ob)\nbpy.ops.wm.save_as_mainfile(filepath=${literal(conflict)}, copy=True)`,
    see: false,
  })
  const conflictCopy = await readFile(conflict)
  const blocked = await recipe(conflict, 'make_lods', { low })
  assert.equal(blocked.job.state, 'failed', blocked.text)
  assert.match(blocked.text, /Refusing to replace existing object/)
  assert.deepEqual(await readFile(conflict), conflictCopy)
  proof.lodConflict = 'Protected the hand-authored LOD and preserved the input file.'

  const rigScene = path.join(work, 'skeletal-probe.blend')
  await tool('py', {
    code: `${fixture}\nbuild_skeletal_probe()\n${expanded ? 'build_probe_actions()\n' : ''}bpy.ops.wm.save_as_mainfile(filepath=${literal(rigScene)}, copy=True)`,
    see: false,
  })
  const skinned = await recipe(rigScene, 'export_unreal', {
    low: 'SK_Probe',
    unreal: {
      preset: 'skeletal',
      armature: 'ProbeRig',
      ...(expanded ? { clips: ['ProbeWalk', 'ProbeStep'] } : {}),
    },
    ...(expanded ? { qa: { armature: 'ProbeRig', influence_limit: 4 } } : {}),
  })
  assert.equal(skinned.job.state, 'completed', skinned.text)
  const skeletal = path.join(work, skinned.id, 'SK_Probe.fbx')
  const checkRig =
    `import bpy\nfor o in list(bpy.context.scene.objects): bpy.data.objects.remove(o,do_unlink=True)\n` +
    `assert bpy.ops.import_scene.fbx(filepath=${literal(skeletal)})=={'FINISHED'}\n` +
    `rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')\n` +
    `assert list(rig.data.bones.keys())==['root']\n` +
    `skin=bpy.data.objects['SK_Probe']\nassert skin.vertex_groups.get('root') and any(m.type=='ARMATURE' and m.object==rig for m in skin.modifiers)`
  const rigProbe = path.join(work, 'verify-skeletal.py')
  await writeFile(rigProbe, checkRig)
  await runExe(exe, ['-b', '--factory-startup', '--python-exit-code', '1', '--python', rigProbe], {
    env: blenderEnv,
  })
  proof.skeletal = skeletal
  if (expanded) {
    const details = JSON.parse(
      await readFile(path.join(work, skinned.id, 'asset-report.json'), 'utf8'),
    )
    assert.deepEqual(
      details.unreal.clips.map((clip) => clip.frames),
      [
        [1, 12],
        [1, 7],
      ],
    )
    assert(details.qa)
    const clipProbe = path.join(work, 'verify-clips.py')
    const clipInputs = details.unreal.clips.map((clip) => [
      clip.file,
      clip.frames[1] - clip.frames[0],
    ])
    await writeFile(
      clipProbe,
      `import bpy, json
for file, expected in json.loads(${literal(JSON.stringify(clipInputs))}):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.fbx(filepath=file) == {"FINISHED"}
    rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    action = rig.animation_data.action
    assert action is not None, file
    begin, end = map(round, action.frame_range)
    assert end - begin == expected, (file, begin, end)
    bpy.context.scene.frame_set(begin)
    first = rig.pose.bones["root"].matrix.translation.copy()
    bpy.context.scene.frame_set(end)
    assert (rig.pose.bones["root"].matrix.translation - first).length > 0.1, file
`,
    )
    await runExe(
      exe,
      ['-b', '--factory-startup', '--python-exit-code', '1', '--python', clipProbe],
      { env: blenderEnv },
    )
    proof.clips = details.unreal.clips
    const failedQa = await recipe(rigScene, 'export_unreal', {
      low: 'SK_Probe',
      unreal: { preset: 'skeletal', armature: 'ProbeRig' },
      qa: { max_tris: 1, armature: 'ProbeRig' },
    })
    assert.equal(failedQa.job.state, 'failed', failedQa.text)
    assert.match(failedQa.text, /Extended delivery QA failed/)
    proof.failedQa = failedQa.id
    await expandedChecks(scene, low, rigScene)
  }
  await writeFile(path.join(work, 'proof.json'), JSON.stringify(proof, null, 2))
  console.log(
    `PASS: ${report.lods.map((lod) => lod.triangles).join(' → ')} triangles; six textures and three FBX files`,
  )
} finally {
  await writeFile(path.join(work, 'blender-gui.log'), blenderLog)
  if (blender && blender.exitCode === null) blender.kill()
  await client.close()
}
