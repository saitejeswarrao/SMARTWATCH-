import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, Bell, Info } from 'lucide-react';

interface Alert {
  id: string;
  message: string;
  type: 'emergency' | 'warning' | 'info';
  timestamp: Date;
}

interface AlertPanelProps {
  alerts: Alert[];
  onDismiss: (id: string) => void;
}

export const AlertPanel: React.FC<AlertPanelProps> = ({ alerts, onDismiss }) => {
  return (
    <div className="fixed top-6 right-6 z-50 flex flex-col gap-3 w-80 pointer-events-none">
      <AnimatePresence>
        {alerts.map((alert) => (
          <motion.div
            key={alert.id}
            layout
            initial={{ opacity: 0, x: 50, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5, transition: { duration: 0.2 } }}
            className={`pointer-events-auto p-4 rounded-xl shadow-2xl flex items-start gap-3 border ${
              alert.type === 'emergency'
                ? 'bg-red-500/90 border-red-400 text-white'
                : alert.type === 'warning'
                ? 'bg-amber-500/90 border-amber-400 text-white'
                : 'bg-blue-500/90 border-blue-400 text-white'
            }`}
          >
            <div className="mt-1">
              {alert.type === 'emergency' ? (
                <AlertTriangle className="w-5 h-5 animate-pulse" />
              ) : alert.type === 'warning' ? (
                <Bell className="w-5 h-5" />
              ) : (
                <Info className="w-5 h-5" />
              )}
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold">{alert.message}</p>
              <p className="text-[10px] opacity-70 mt-1 uppercase tracking-wider">
                System Alert • Just Now
              </p>
            </div>
            <button
              onClick={() => onDismiss(alert.id)}
              className="hover:bg-white/20 rounded p-1 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};
