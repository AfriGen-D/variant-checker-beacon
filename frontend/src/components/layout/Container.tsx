import { HTMLAttributes, ReactNode } from 'react';

interface ContainerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

export function Container({ children, size = 'lg', className = '', ...props }: ContainerProps) {
  const sizeClasses = {
    sm: 'max-w-3xl',
    md: 'max-w-5xl',
    lg: 'max-w-7xl',
    xl: 'max-w-screen-2xl',
    full: 'max-w-full',
  };

  return (
    <div className={`${sizeClasses[size]} mx-auto px-4 sm:px-6 lg:px-8 ${className}`} {...props}>
      {children}
    </div>
  );
}
