import path from 'node:path'
import { errorLine, toolError } from '../errors.js'

async function provider(args: Record<string, unknown>) {
  const action = args.op
  if (action !== 'check' && action !== 'submit' && action !== 'collect')
    throw new Error('asset_provider op must be check, submit or collect')
  if (typeof args.file !== 'string' || !path.isAbsolute(args.file) || !/\.json$/i.test(args.file))
    throw new Error('asset_provider file must be an absolute JSON manifest path')
  if (action === 'submit' && args.allow_upload !== true)
    throw new Error(
      'Submitting sends the selected files to Fal and can incur charges. Set allow_upload only when authorized.',
    )
  const url = new URL('../../../runtime/ext/fal/fal-batch.mjs', import.meta.url)
  const { runBatch } = (await import(url.href)) as {
    runBatch(command: string, filename: string): Promise<unknown[]>
  }
  return { provider: 'fal', operation: action, jobs: await runBatch(action, args.file) }
}

export async function executeAssetProvider(args: Record<string, unknown>) {
  try {
    return await provider(args)
  } catch (error) {
    return toolError(
      'asset_provider_error',
      errorLine(error),
      'Use op=check to validate the local manifest before retrying.',
    )
  }
}
