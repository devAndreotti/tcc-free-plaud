import { createContext } from 'react';
import type { QueueState } from '../hooks/useIndexJob';

export const QueueContext = createContext<QueueState | null>(null);
