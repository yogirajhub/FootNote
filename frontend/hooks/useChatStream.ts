'use client';
import { useCallback, useRef, useState } from 'react';
import { chatService } from '../services/chat';
import type { ChatRequest, Evidence, Panels, SSEEvent } from '../types/api';

export type StreamStatus = 'idle' | 'streaming' | 'done' | 'error';

export interface StreamState {
  answer: string;
  evidence: Evidence | null;
  panels: Panels;
  intent: string | null;
  status: StreamStatus;
  error: string | null;
  conversationId: string | null;
  processingMs: number | null;
}

const INIT: StreamState = {
  answer: '',
  evidence: null,
  panels: {},
  intent: null,
  status: 'idle',
  error: null,
  conversationId: null,
  processingMs: null,
};

export function useChatStream() {
  const [state, setState] = useState<StreamState>(INIT);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (request: ChatRequest) => {
    // Cancel any in-flight request
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setState({ ...INIT, status: 'streaming' });

    try {
      await chatService.streamMessage(
        request,
        (event: SSEEvent) => {
          if (event.type === 'metadata') {
            setState(s => ({ ...s, intent: event.intent }));
          } else if (event.type === 'delta') {
            setState(s => ({ ...s, answer: s.answer + event.content }));
          } else if (event.type === 'done') {
            setState(s => ({ ...s, status: 'done', processingMs: event.processing_time_ms }));
          } else if (event.type === 'error') {
            setState(s => ({ ...s, status: 'error', error: event.message }));
          }
        },
        ctrl.signal,
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setState(s => ({
        ...s,
        status: 'error',
        error: err instanceof Error ? err.message : 'An unknown error occurred',
      }));
    }
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setState(s => ({ ...s, status: 'idle' }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INIT);
  }, []);

  return { state, send, abort, reset };
}
