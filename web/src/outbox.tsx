// STAND-IN for strata-react's `createOutbox`, `useOutbox`, `useOutboxStarted` and `OutboxStatus`
// (jburnhams/strata-react#308), copied from that PR so Flashtap does not wait for its release; replace these imports
// with strata-react's and delete this file once it is released (docs/implementation-plan.md, "Stand-ins"). The reasons
// for its shape are in that PR's src/query/outbox.ts: writes kept in localStorage and sent oldest first; a 4xx is
// refused and listed with the server's reason, anything else waits and is retried (2 s doubling to a minute, at once on
// `online` or when the page is shown); every write must be idempotent on the server.
import { CircleAlert, CloudOff, LoaderCircle } from 'lucide-react'
import * as React from 'react'
import { appBase, Button, cn, fetchJson, format, HttpError, withBase } from 'strata-react'

/** One write to send: a JSON body to a root-relative path of the app's own server. */
export type OutboxRequest = {
  method: "POST" | "PUT" | "PATCH" | "DELETE";
  /** Root-relative (`/api/attempts`); the app's base is put in front when it is sent. */
  path: string;
  json?: unknown;
};

/** A write as it waits: the request, its id, when it was queued, what it follows and the words a person sees for it. */
export type OutboxItem = OutboxRequest & {
  id: string;
  queuedAt: string;
  /** The id of an earlier write this one depends on. */
  after?: string;
  /** What it is, in the product's words ("Fox's answer"), for the refused list. */
  label?: string;
};

/** A write the server refused, kept to be shown until dismissed. */
export type OutboxRefusal = { id: string; label?: string; reason: string; at: string };

/** Where the outbox stands. */
export type OutboxSnapshot = {
  /** Writes not yet sent. */
  waiting: number;
  /** A send is under way. */
  sending: boolean;
  /** Why the last try stopped, when writes are waiting: "The server could not be reached." */
  problem: string | null;
  /** When it tries again on its own, while writes are waiting after a failure. */
  retryAt: Date | null;
  /** Refused writes, oldest first. */
  refused: readonly OutboxRefusal[];
  /** False when the browser gives no storage: the writes wait in this page only. */
  persisted: boolean;
};

/** How a write's first try went. */
export type Delivery = "sent" | "waiting" | "refused";

/** Options for `createOutbox`. */
export type OutboxOptions = {
  /** Names the queue in storage: `strata:outbox:<name>`. One per kind of work the app keeps. */
  name: string;
  /** Sends one write; default `fetchJson` to the path with the app's base. Throw an `HttpError` to have a 4xx refused. */
  send?: (item: OutboxItem) => Promise<unknown>;
  /** Where the queue is kept. Default `window.localStorage`; `null` keeps it in memory. */
  storage?: Storage | null;
  /** The first wait before trying again, doubled each time up to `maxRetryMs`. Default 2000. */
  retryMs?: number;
  /** Default 60000. */
  maxRetryMs?: number;
};

/** A queue of writes kept on the device and sent when the server can take them. */
export type Outbox = {
  /** Queues a write and tries to send the queue. `id` defaults to a random one; give the write's own id (an event id) so a refusal can be matched. */
  add(request: OutboxRequest & { id?: string; after?: string; label?: string }): { id: string; delivered: Promise<Delivery> };
  /** Sends what waits, oldest first, until one fails. Resolves when this pass ends. */
  flush(): Promise<void>;
  snapshot(): OutboxSnapshot;
  subscribe(listener: () => void): () => void;
  /** Calls `listener` with each write this page has sent, whenever it went (the first try, a retry, or a write an earlier
   * visit left): refresh what the server's answer changes here, as a `delivered` first try misses later sends. */
  onSent(listener: (item: OutboxItem) => void): () => void;
  /** Forgets a refused write (or all of them). */
  dismiss(id?: string): void;
  /** Sends what waits now, and again whenever the browser comes back online, the page is shown or another tab adds. Returns the stop. */
  start(): () => void;
};

type Kept = { items: OutboxItem[]; refused: OutboxRefusal[] };

const REFUSED_KEPT = 50; // a list a person reads, not a log: the oldest refusals go first

/** Whether a failure is the server's answer for good (refused) rather than for now (waiting). */
export function isRefusal(error: unknown): error is HttpError {
  return error instanceof HttpError && error.status >= 400 && error.status < 500 && ![401, 403, 408, 425, 429].includes(error.status);
}

function problemOf(error: unknown): string {
  if (error instanceof HttpError) {
    if (error.status === 401 || error.status === 403) return "Sign in again to send them.";
    if (error.status === 429) return "The server asked to wait.";
    return error.reason ?? "The server had a problem.";
  }
  return "The server could not be reached.";
}

function defaultStorage(): Storage | null {
  try {
    const s = window.localStorage;
    const probe = "strata:outbox:probe";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

function randomId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** A queue of writes kept on the device (localStorage) and sent in order when the server can take them; see `useOutbox` and `OutboxStatus`. */
export function createOutbox({ name, send, storage, retryMs = 2000, maxRetryMs = 60000 }: OutboxOptions): Outbox {
  const key = `strata:outbox:${name}`;
  const store = storage === undefined ? defaultStorage() : storage; // no window (SSR) is no storage: the probe throws
  const post = send ?? ((item: OutboxItem) => fetchJson(withBase(item.path, appBase()), { method: item.method, json: item.json }));
  let memory: Kept = { items: [], refused: [] };
  let persisted = store !== null;
  let sending = false;
  let problem: string | null = null;
  let retryAt: Date | null = null;
  let wait = retryMs;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let running: Promise<void> | null = null;
  // Every caller waiting on a write's first try (the same id can be added twice), and ids whose add is still waiting for
  // the write lock: a pass that finds the queue empty must not take those for sent by another tab.
  const firstTry = new Map<string, ((d: Delivery) => void)[]>();
  const adding = new Set<string>();
  const listeners = new Set<() => void>();
  const sentListeners = new Set<(item: OutboxItem) => void>();
  let snap: OutboxSnapshot | null = null;

  // Read before every change, so two tabs adding and removing do not overwrite each other's work.
  const read = (): Kept => {
    if (!persisted || !store) return memory;
    try {
      const raw = JSON.parse(store.getItem(key) ?? "null") as Partial<Kept> | null;
      return { items: Array.isArray(raw?.items) ? raw.items : [], refused: Array.isArray(raw?.refused) ? raw.refused : [] };
    } catch {
      return memory;
    }
  };
  const write = (kept: Kept) => {
    memory = kept;
    if (persisted && store) {
      try {
        store.setItem(key, JSON.stringify(kept));
      } catch {
        persisted = false; // full or taken away: keep going in memory, and say so
      }
    }
    changed();
  };
  const changed = () => {
    snap = null;
    for (const l of listeners) l();
  };
  const settle = (id: string, d: Delivery) => {
    for (const resolve of firstTry.get(id) ?? []) resolve(d);
    firstTry.delete(id);
  };
  const lockManager = () => (navigator as Navigator & { locks?: LockManager }).locks; // a browser's, and Node's from 22
  // One change to the stored queue, read and written under the write lock, so no other tab's change falls between.
  const mutate = (change: (kept: Kept) => Kept): Promise<void> => {
    const apply = () => write(change(read()));
    const locks = persisted ? lockManager() : undefined; // in memory, no other tab shares it
    if (!locks) {
      apply();
      return Promise.resolve();
    }
    return locks.request(`${key}:write`, apply);
  };

  const refuse = (kept: Kept, item: OutboxItem, reason: string): Kept => ({
    items: kept.items.filter((x) => x.id !== item.id),
    refused: [...kept.refused, { id: item.id, label: item.label, reason, at: new Date().toISOString() }].slice(-REFUSED_KEPT),
  });

  const pass = async () => {
    sending = true;
    changed();
    try {
      for (;;) {
        const kept = read();
        const item = kept.items[0];
        if (!item) {
          // Writes this tab queued that another tab sent or refused first (it held the lock): their first try is over.
          for (const id of [...firstTry.keys()]) {
            if (!adding.has(id)) settle(id, kept.refused.some((r) => r.id === id) ? "refused" : "sent");
          }
          problem = null;
          retryAt = null;
          wait = retryMs;
          return;
        }
        const parent = item.after ? kept.refused.find((r) => r.id === item.after) : undefined;
        if (parent) {
          await mutate((k) => refuse(k, item, `Not sent, as what it follows was refused: ${parent.reason}`));
          settle(item.id, "refused");
          continue;
        }
        try {
          await post(item);
          await mutate((k) => ({ ...k, items: k.items.filter((x) => x.id !== item.id) }));
          settle(item.id, "sent");
          for (const l of sentListeners) l(item);
        } catch (error) {
          if (!isRefusal(error)) {
            problem = problemOf(error);
            retryAt = new Date(Date.now() + wait);
            clearTimeout(timer);
            timer = setTimeout(() => void flush(), wait);
            wait = Math.min(wait * 2, maxRetryMs);
            for (const x of read().items) settle(x.id, "waiting");
            return;
          }
          const reason = error.reason ?? `${error.status} ${error.statusText}`;
          await mutate((k) => refuse(k, item, reason));
          settle(item.id, "refused");
        }
      }
    } finally {
      sending = false;
      changed();
    }
  };

  // A flush asked for while a pass runs is a new pass after it: the running one may already have stopped at a failure
  // (its `delivered` answers settle before it ends), and "Send now" or the network coming back must try again.
  const flush = (): Promise<void> => {
    if (running) return running.then(flush);
    clearTimeout(timer);
    const locks = lockManager(); // SSR never flushes
    const run = locks ? locks.request(key, pass) : pass();
    running = run.finally(() => {
      running = null;
    });
    return running;
  };

  return {
    add({ id = randomId(), ...request }) {
      const delivered = new Promise<Delivery>((resolve) => firstTry.set(id, [...(firstTry.get(id) ?? []), resolve]));
      const item: OutboxItem = { ...request, id, queuedAt: new Date().toISOString() };
      adding.add(id);
      void mutate((k) => (k.items.some((x) => x.id === id) ? k : { ...k, items: [...k.items, item] })).then(() => {
        adding.delete(id);
        // A pass under way picks the new write up; one that already ended on a failure does not, so it waits for the
        // retry unless no pass is running, when this starts one.
        if (running) void running.then(() => (firstTry.has(id) ? flush() : undefined));
        else void flush();
      });
      return { id, delivered };
    },
    flush,
    snapshot() {
      if (!snap) {
        const kept = read();
        snap = { waiting: kept.items.length, sending, problem: kept.items.length ? problem : null, retryAt: kept.items.length ? retryAt : null, refused: kept.refused, persisted };
      }
      return snap;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    onSent(listener) {
      sentListeners.add(listener);
      return () => sentListeners.delete(listener);
    },
    dismiss(id) {
      void mutate((k) => ({ ...k, refused: id === undefined ? [] : k.refused.filter((r) => r.id !== id) }));
    },
    start() {
      // Called from an effect, so in a browser: `window` and `document` are there.
      const now = () => {
        wait = retryMs; // the network says it is back: try now and from the first wait again
        void flush();
      };
      const shown = () => {
        if (document.visibilityState === "visible") now();
      };
      const other = (e: StorageEvent) => {
        if (e.key !== key) return;
        changed();
        if (e.newValue) void flush(); // after any pass under way, which may have stopped before this write was there
      };
      window.addEventListener("online", now);
      document.addEventListener("visibilitychange", shown);
      window.addEventListener("storage", other);
      void flush();
      return () => {
        clearTimeout(timer);
        window.removeEventListener("online", now);
        document.removeEventListener("visibilitychange", shown);
        window.removeEventListener("storage", other);
      };
    },
  };
}

/** Where `outbox` stands, re-rendering when it changes. Call `outbox.start()` once for the app (`useOutboxStarted`). */
export function useOutbox(outbox: Outbox): OutboxSnapshot {
  return React.useSyncExternalStore(outbox.subscribe, outbox.snapshot, outbox.snapshot);
}

/** Starts `outbox` (sends what waits, and again on reconnect) for as long as the calling component is mounted: put it in the app's shell. */
export function useOutboxStarted(outbox: Outbox): void {
  React.useEffect(() => outbox.start(), [outbox]);
}

/** Props for `OutboxStatus`. */
export type OutboxStatusProps = {
  outbox: Outbox;
  /** What a write is, singular, for `format.count`: "answer" gives "3 answers kept on this device". */
  noun: string;
  className?: string;
};

/** Says how many writes wait on this device and why, with Send now, and lists any the server refused; renders nothing while all is sent. */
export function OutboxStatus({ outbox, noun, className }: OutboxStatusProps) {
  const s = useOutbox(outbox);
  if (s.waiting === 0 && s.refused.length === 0) return null;
  const count = format.count(s.waiting, noun);
  return (
    <div className={cn("grid gap-2 type-body-sm", className)}>
      {s.waiting > 0 && (
        <p role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
          {s.sending ? (
            <LoaderCircle aria-hidden className="size-4 shrink-0 motion-safe:animate-spin" />
          ) : (
            <CloudOff aria-hidden className="size-4 shrink-0" />
          )}
          <span>
            {s.sending ? `Sending ${count}…` : `${count} kept on this device.`}
            {!s.sending && s.problem && ` ${s.problem}`}
            {!s.sending && s.retryAt && ` Trying again at ${format.clock(s.retryAt)}.`}
            {!s.persisted && " They are kept only while this page is open."}
          </span>
          {!s.sending && (
            <Button size="sm" onClick={() => void outbox.flush()}>
              Send now
            </Button>
          )}
        </p>
      )}
      {s.refused.length > 0 && (
        <div role="status" className="grid gap-1 text-danger">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <CircleAlert aria-hidden className="size-4 shrink-0" />
            <span>
              {s.refused.length === 1 ? `The server refused 1 ${noun}; it will not be sent.` : `The server refused ${format.count(s.refused.length, noun)}; they will not be sent.`}
            </span>
            <Button size="sm" variant="ghost" onClick={() => outbox.dismiss()}>
              Dismiss
            </Button>
          </p>
          <ul className="grid gap-1 pl-6">
            {s.refused.map((r) => (
              <li key={r.id}>
                {r.label ? `${r.label}: ` : ""}
                {r.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
