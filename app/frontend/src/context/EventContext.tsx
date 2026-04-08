import React, { createContext, useContext, useEffect, useRef } from 'react';
import { API_URLS } from '../services/api';
import type { UnifiedEvent } from '../hooks/useUnifiedEvents';

type Subscriber = (event: UnifiedEvent) => void;

interface EventContextType {
  subscribe: (callback: Subscriber) => () => void;
}

const EventContext = createContext<EventContextType | null>(null);

export const EventProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const subscribersRef = useRef<Set<Subscriber>>(new Set());

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const token = localStorage.getItem('token') || document.cookie.match(/(?:^|; )access_token=([^;]*)/)?.[1] || '';
      const wsUrl = `${API_URLS.EVENTS_WS}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload: UnifiedEvent = JSON.parse(event.data);
          subscribersRef.current.forEach((cb) => cb(payload));
        } catch (e) {
          console.error('Failed to parse unified event:', e);
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  const subscribe = (callback: Subscriber) => {
    subscribersRef.current.add(callback);
    return () => {
      subscribersRef.current.delete(callback);
    };
  };

  return (
    <EventContext.Provider value={{ subscribe }}>
      {children}
    </EventContext.Provider>
  );
};

export const useEventContext = () => {
  const ctx = useContext(EventContext);
  if (!ctx) throw new Error('useEventContext must be used within EventProvider');
  return ctx;
};
