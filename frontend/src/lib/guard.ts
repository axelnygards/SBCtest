/**
 * Client-side circuit breakers. The solver runs on the server, but the browser still needs
 * to protect itself: a request can hang and a large sync can block the main thread.
 */

export class TimeoutError extends Error {
  constructor(what: string, ms: number) {
    super(`${what} avbröts efter ${Math.round(ms / 1000)} s`);
    this.name = "TimeoutError";
  }
}

/** fetch with a hard timeout (AbortController); the server has its own, shorter limit. */
export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  ms = 45_000,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  init.signal?.addEventListener("abort", () => ctrl.abort());
  try {
    return await fetchImpl(url, { ...init, signal: ctrl.signal });
  } catch (e) {
    if (ctrl.signal.aborted && !init.signal?.aborted) throw new TimeoutError("Förfrågan", ms);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Run heavy work in a Web Worker and terminate() it after `ms`. terminate() stops the
 * worker thread even inside an infinite loop, so the page and the phone stay responsive.
 */
export function runWorker<TIn, TOut>(
  makeWorker: () => Worker,
  input: TIn,
  ms: number,
): Promise<TOut> {
  return new Promise((resolve, reject) => {
    const w = makeWorker();
    const timer = setTimeout(() => {
      w.terminate();
      reject(new TimeoutError("Bakgrundsjobbet", ms));
    }, ms);
    w.onmessage = (e: MessageEvent<{ ok: boolean; result?: TOut; error?: string }>) => {
      clearTimeout(timer);
      w.terminate();
      if (e.data.ok) resolve(e.data.result as TOut);
      else reject(new Error(e.data.error));
    };
    w.onerror = (e) => {
      clearTimeout(timer);
      w.terminate();
      reject(new Error(e.message));
    };
    w.postMessage(input);
  });
}
