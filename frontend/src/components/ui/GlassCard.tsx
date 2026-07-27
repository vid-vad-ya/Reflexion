import React from 'react';
import { motion } from 'framer-motion';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  animate?: boolean;
  hoverable?: boolean;
  onClick?: () => void;
}

export default function GlassCard({
  children,
  className = '',
  animate = true,
  hoverable = false,
  onClick,
}: GlassCardProps) {
  const CardComponent = animate ? motion.div : 'div';
  
  const animationProps = animate
    ? {
        initial: { opacity: 0, y: 10 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
        whileHover: hoverable ? { y: -2, transition: { duration: 0.2 } } : undefined,
      }
    : {};

  return (
    // @ts-ignore
    <CardComponent
      {...animationProps}
      onClick={onClick}
      className={`glass-panel ${hoverable ? 'cursor-pointer hover:border-white/10' : ''} ${className}`}
    >
      {children}
    </CardComponent>
  );
}
