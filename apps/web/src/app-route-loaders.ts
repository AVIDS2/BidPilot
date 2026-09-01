type RouteLoader = () => Promise<unknown>;

const CHUNK_RECOVERY_PARAM = '__docpilot_chunk_recovery';
const CHUNK_RECOVERY_KEY_PREFIX = 'docpilot:chunk-recovery:';

export function isDynamicImportError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /failed to fetch dynamically imported module|importing a module script failed|loading chunk|chunkloaderror/i.test(
    message
  );
}

function recoveryKey(chunkName: string) {
  return `${CHUNK_RECOVERY_KEY_PREFIX}${chunkName}:${window.location.pathname}`;
}

function recoverOnce(chunkName: string) {
  if (typeof window === 'undefined') return false;
  try {
    const key = recoveryKey(chunkName);
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, '1');
    const url = new URL(window.location.href);
    url.searchParams.set(CHUNK_RECOVERY_PARAM, String(Date.now()));
    window.location.replace(url.href);
    return true;
  } catch {
    return false;
  }
}

export async function loadWithChunkRecovery<T>(
  loader: () => Promise<T>,
  chunkName: string
): Promise<T> {
  try {
    return await loader();
  } catch (error) {
    if (isDynamicImportError(error) && recoverOnce(chunkName)) throw error;
    throw error;
  }
}

export const routeLoaders: Record<string, RouteLoader> = {
  agent: () => import('./features/agent/agent-workspace-page')
};
