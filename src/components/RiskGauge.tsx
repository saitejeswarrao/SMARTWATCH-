import React from 'react';
import { motion } from 'motion/react';

interface RiskGaugeProps {
  label: string;
  value: number; // 0 to 1
  color: string;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({ label, value, color }) => {
  const percentage = Math.min(100, Math.max(0, value * 100));
  
  return (
    <div className="flex flex-col gap-1 w-full">
      <div className="flex justify-between items-center text-[10px] font-mono tracking-wider uppercase text-slate-500">
        <span>{label}</span>
        <span>{percentage.toFixed(0)}% RISK</span>
      </div>
      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden border border-white/5">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
        />
      </div>
    </div>
  );
};
