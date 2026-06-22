"use client";

/** A reconnecting EventSource wrapper.
 *
 * The native EventSource only auto-retries while the connection is merely
 * interrupted — a hard error (or our own `onerror` closing it) leaves the stream
 * permanently dead, so live updates freeze until a manual page refresh. This
 * wrapper reconnects with exponential backoff + jitter, recreating listeners on
 * each attempt, and stops cleanly when the caller is done or unmounts.
 */

export interface ReconnectingSSE {
  close: () => void;
}

interface Options {
  /** Attach listeners to a freshly (re)connected EventSource. `done()` ends the
   *  stream for good (e.g. a terminal event arrived) — no further reconnects. */
  setup: (es: EventSource, done: () => void) => void;
  onOpen?: () => void;
  onError?: () => void;
  maxDelayMs?: number;
}

export function openReconnectingSSE(urlFactory: () => string, opts: Options): ReconnectingSSE {
  let es: EventSource | null = null;
  let stopped = false;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const maxDelay = opts.maxDelayMs ?? 30_000;

  const done = () => {
    stopped = true;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (es) {
      es.close();
      es = null;
    }
  };

  const connect = () => {
    if (stopped) return;
    const source = new EventSource(urlFactory());
    es = source;

    source.onopen = () => {
      attempt = 0; // reset backoff after a successful connect
      opts.onOpen?.();
    };

    opts.setup(source, done);

    source.onerror = () => {
      opts.onError?.();
      source.close();
      if (es === source) es = null;
      if (stopped) return;
      const delay = Math.min(maxDelay, 1000 * 2 ** attempt) + Math.floor(Math.random() * 250);
      attempt += 1;
      timer = setTimeout(connect, delay);
    };
  };

  connect();
  return { close: done };
}
