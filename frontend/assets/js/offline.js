/**
 * Offline Execution Mode (§20B) — client side.
 *
 * Records created while offline are stored in localStorage (device storage,
 * NOT the server) with a local id, device timestamp and sync status.
 * When connectivity returns they are replayed FIFO; the server endpoint
 * applies idempotent dedupe (local_id) and detects version conflicts
 * without ever overwriting the server record.
 */
import { api, Session } from './core.js?v=11';

const KEY = 'cmms_offline_queue';

export function offlineQueue() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}

function saveQueue(q) { localStorage.setItem(KEY, JSON.stringify(q)); }

/** Enqueue an offline record for a work order. */
export function enqueue(woid, record) {
  const q = offlineQueue();
  q.push({
    woid,
    record: {
      local_id: record.local_id || `L-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      device_at: new Date().toISOString(),
      status: 'pending',
      ...record,
    },
    created_at: Date.now(),
  });
  saveQueue(q);
}

export function pendingCount() { return offlineQueue().length; }

/** Replay pending records FIFO, grouped per work order. */
export async function flushQueue() {
  const q = offlineQueue();
  if (!q.length) return { sent: 0, conflicts: 0 };
  const byWo = {};
  for (const item of q) (byWo[item.woid] ||= []).push(item);

  let sent = 0, conflicts = 0;
  const remaining = [];

  for (const [woid, items] of Object.entries(byWo)) {
    try {
      const wo = await api(`/work-orders/${woid}`);
      const res = await api(`/work-orders/${woid}/offline-sync`, {
        method: 'POST',
        body: {
          base_version: wo.version,
          records: items.map((i) => ({
            local_id: i.record.local_id,
            type: i.record.type,
            action: i.record.action || null,
            text: i.record.text || null,
            kind: i.record.kind || 'text',
            device_at: i.record.device_at,
          })),
        },
      });
      sent += res.applied || 0;
    } catch (e) {
      if (e.status === 409 && e.detail && e.detail.error === 'offline_conflict') {
        // conflict kept on server; manager resolves (§20B) — drop from device
        conflicts += 1;
      } else {
        remaining.push(...items); // keep for the next attempt
      }
    }
  }
  saveQueue(remaining);
  return { sent, conflicts, kept: remaining.length };
}

/** Live connectivity watcher: pill state + automatic flush on reconnect. */
export function watchConnectivity(setConn) {
  const update = () => {
    const pending = pendingCount();
    if (!navigator.onLine) setConn('offline');
    else if (pending) setConn('syncing');
    else setConn('online');
  };
  window.addEventListener('online', async () => {
    update();
    if (pendingCount()) {
      const res = await flushQueue();
      update();
      return res;
    }
  });
  window.addEventListener('offline', update);
  update();
  return update;
}
