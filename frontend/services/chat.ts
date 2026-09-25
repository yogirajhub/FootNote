import { api } from './api';
import type { ChatRequest, ChatResponse, ConversationResponse, MessageResponse, SSEEvent } from '../types/api';

const API_URL = typeof window === 'undefined'
  ? (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000/api')
  : '/api';
const USER_ID = 'demo_user_001';

export const chatService = {
  async sendMessage(
    documentId: string,
    message: string,
    conversationId?: string,
    mode: 'document' | 'library' = 'document',
    documentIds?: string[]
  ): Promise<ChatResponse> {
    const { data } = await api.post<ChatResponse>('/chat', {
      document_id: documentId,
      message,
      conversation_id: conversationId,
      mode,
      document_ids: documentIds,
    });
    return data;
  },

  streamMessage(
    request: ChatRequest,
    onEvent: (event: SSEEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    return fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-user-id': USER_ID,
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(request),
      signal,
    }).then(async (res) => {
      if (!res.ok) {
        throw new Error(`Stream failed: ${res.status}`);
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6)) as SSEEvent;
                onEvent(event);
              } catch {
                // skip malformed
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    });
  },

  async listConversations(documentId?: string) {
    const { data } = await api.get<{ conversations: ConversationResponse[]; total: number }>('/conversations', {
      params: { document_id: documentId },
    });
    return data;
  },

  async getConversation(id: string) {
    const { data } = await api.get<{ conversation: ConversationResponse; messages: MessageResponse[] }>(
      `/conversations/${id}`
    );
    return data;
  },
};

