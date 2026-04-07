import { useEffect } from 'react';
import { useEventContext } from '../context/EventContext';

export type UnifiedEvent = 
  | { type: 'device_status'; data: { device_id: number; status: 'online' | 'offline' | 'warning'; provisioning_status?: 'pending' | 'active' | 'expired' } }
  | { type: 'alert'; data: any };

export function useUnifiedEvents(onEvent: (event: UnifiedEvent) => void) {
  const { subscribe } = useEventContext();

  useEffect(() => {
    // Subscribe the callback to the global event stream
    const unsubscribe = subscribe(onEvent);
    // Cleanup on unmount
    return () => unsubscribe();
  }, [subscribe, onEvent]);
}
