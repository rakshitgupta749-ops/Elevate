'use client';

import * as React from 'react';
import { motion, type Transition } from 'framer-motion';
import { cn } from '@/lib/utils';

interface ProgressContextType {
  value: number;
  max: number;
}

const ProgressContext = React.createContext<ProgressContextType | null>(null);

export function useProgress(): ProgressContextType {
  const context = React.useContext(ProgressContext);
  if (!context) {
    throw new Error('useProgress must be used within a Progress component');
  }
  return context;
}

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  children?: React.ReactNode;
}

export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ value = 0, max = 100, className, children, ...props }, ref) => {
    const clampedValue = Math.min(Math.max(value, 0), max);

    return (
      <ProgressContext.Provider value={{ value: clampedValue, max }}>
        <div
          ref={ref}
          role="progressbar"
          aria-valuenow={clampedValue}
          aria-valuemin={0}
          aria-valuemax={max}
          className={cn('relative w-full space-y-2', className)}
          {...props}
        >
          {children}
        </div>
      </ProgressContext.Provider>
    );
  }
);
Progress.displayName = 'Progress';

export interface ProgressLabelProps extends React.HTMLAttributes<HTMLSpanElement> {
  children?: React.ReactNode;
}

export const ProgressLabel = React.forwardRef<HTMLSpanElement, ProgressLabelProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn('text-sm font-semibold text-slate-200 tracking-wide', className)}
        {...props}
      >
        {children}
      </span>
    );
  }
);
ProgressLabel.displayName = 'ProgressLabel';

export interface ProgressValueProps extends React.HTMLAttributes<HTMLSpanElement> {
  duration?: number;
}

export const ProgressValue = React.forwardRef<HTMLSpanElement, ProgressValueProps>(
  ({ className, duration = 400, ...props }, ref) => {
    const { value } = useProgress();
    const [displayVal, setDisplayVal] = React.useState(value);

    React.useEffect(() => {
      const start = displayVal;
      const end = value;
      if (start === end) return;

      const startTime = performance.now();
      let frameId: number;

      const update = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Smooth ease-out quad
        const ease = 1 - (1 - progress) * (1 - progress);
        const current = Math.round(start + (end - start) * ease);
        setDisplayVal(current);

        if (progress < 1) {
          frameId = requestAnimationFrame(update);
        }
      };

      frameId = requestAnimationFrame(update);
      return () => cancelAnimationFrame(frameId);
    }, [value, duration]);

    return (
      <span
        ref={ref}
        className={cn('font-mono font-bold text-indigo-400 tabular-nums', className)}
        {...props}
      >
        {displayVal}
      </span>
    );
  }
);
ProgressValue.displayName = 'ProgressValue';

export interface ProgressTrackProps extends React.HTMLAttributes<HTMLDivElement> {
  indicatorClassName?: string;
  transition?: Transition;
  children?: React.ReactNode;
}

export const ProgressTrack = React.forwardRef<HTMLDivElement, ProgressTrackProps>(
  ({ className, indicatorClassName, transition = { type: 'spring', stiffness: 90, damping: 20 }, children, ...props }, ref) => {
    const { value, max } = useProgress();
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    return (
      <div
        ref={ref}
        className={cn(
          'relative h-2.5 w-full overflow-hidden rounded-full bg-slate-800/80 border border-slate-700/60 shadow-inner',
          className
        )}
        {...props}
      >
        {children ? (
          children
        ) : (
          <motion.div
            className={cn(
              'h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-teal-400 shadow-md shadow-indigo-500/50',
              indicatorClassName
            )}
            initial={{ width: 0 }}
            animate={{ width: `${percentage}%` }}
            transition={transition}
          />
        )}
      </div>
    );
  }
);
ProgressTrack.displayName = 'ProgressTrack';

export interface ProgressIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  transition?: Transition;
}

export const ProgressIndicator = React.forwardRef<HTMLDivElement, ProgressIndicatorProps>(
  ({ className, transition = { type: 'spring', stiffness: 90, damping: 20 }, ...props }, ref) => {
    const { value, max } = useProgress();
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    return (
      <motion.div
        ref={ref}
        className={cn(
          'h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-teal-400 shadow-md shadow-indigo-500/50',
          className
        )}
        initial={{ width: 0 }}
        animate={{ width: `${percentage}%` }}
        transition={transition}
        {...(props as any)}
      />
    );
  }
);
ProgressIndicator.displayName = 'ProgressIndicator';

export const BaseProgressDemo: React.FC = () => {
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) return 100;
        return prev + 25;
      });
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  React.useEffect(() => {
    if (progress >= 100) {
      const resetTimeout = setTimeout(() => setProgress(0), 4000);
      return () => clearTimeout(resetTimeout);
    }
  }, [progress]);

  return (
    <Progress value={progress} className="w-[300px] space-y-2">
      <div className="flex items-center justify-between gap-1">
        <ProgressLabel>Export data</ProgressLabel>
        <span className="text-sm">
          <ProgressValue /> %
        </span>
      </div>
      <ProgressTrack />
    </Progress>
  );
};
