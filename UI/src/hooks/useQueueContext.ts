import { useContext } from 'react';
import { QueueContext } from '../contexts/QueueContextObject';
import type { QueueState } from './useIndexJob';

export function useQueueContext(): QueueState {
  const ctx = useContext(QueueContext);
  if (!ctx) {
    throw new Error('useQueueContext deve ser usado dentro de <QueueProvider>');
  }
  return ctx;
}
