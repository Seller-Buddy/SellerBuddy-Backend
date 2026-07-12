import type { ClientMessage, ServerMessage } from '../../../core/src/messages.js';
import { isBrowserRuntime } from '../runtime.js';
import { PostMessageTransport } from './postMessageTransport.js';
import type { MessageTransport } from './types.js';
import { WebSocketTransport } from './webSocketTransport.js';

const BROWSER_DEV_LAYOUT_STORAGE_KEY = 'pixel-agents.dev.layout';

class BrowserDevTransport implements MessageTransport {
  send(message: ClientMessage): void {
    if (message.type === 'saveLayout') {
      try {
        window.localStorage.setItem(BROWSER_DEV_LAYOUT_STORAGE_KEY, JSON.stringify(message.layout));
        console.debug('[BrowserDevTransport] layout saved to localStorage');
      } catch (err) {
        console.warn('[BrowserDevTransport] failed to save layout to localStorage:', err);
      }
      return;
    }

    console.debug('[BrowserDevTransport] send ignored:', message);
  }

  onMessage(handler: (message: ServerMessage) => void): () => void {
    const listener = (e: MessageEvent) => handler(e.data as ServerMessage);
    window.addEventListener('message', listener);
    return () => window.removeEventListener('message', listener);
  }

  dispose(): void {
    // No cleanup needed beyond per-listener unsubscribe.
  }
}

function createTransport(): MessageTransport {
  if (!isBrowserRuntime) {
    return new PostMessageTransport();
  }
  if (import.meta.env.DEV) {
    return new BrowserDevTransport();
  }
  // Standalone browser: connect via WebSocket to the same host serving the SPA
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  const ws = new WebSocketTransport(wsUrl);
  ws.connect();
  return ws;
}

/** Singleton transport instance. Import this everywhere instead of vscodeApi. */
export const transport: MessageTransport = createTransport();
export type { MessageTransport } from './types.js';
