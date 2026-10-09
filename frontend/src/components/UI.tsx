import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'quiet'
  loading?: boolean
}

export function Button({ variant = 'primary', loading = false, disabled, className = '', children, type = 'button', ...props }: ButtonProps) {
  return <button {...props} type={type} disabled={disabled || loading} aria-busy={loading || undefined} className={`button button-${variant} ${className}`}>{loading && <span className="spinner" aria-hidden="true" />}{children}</button>
}

interface CardProps extends HTMLAttributes<HTMLElement> {
  tone?: 'white' | 'leaf' | 'butter'
  elevated?: boolean
}

export function Card({ tone = 'white', elevated = false, className = '', ...props }: CardProps) {
  return <section {...props} className={`card card-${tone} ${elevated ? 'card-elevated' : ''} ${className}`} />
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`field ${className}`} />
}

export function Textarea({ className = '', ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`field ${className}`} />
}

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`field ${className}`} />
}

export function Badge({ children, tone = 'butter' }: { children: ReactNode; tone?: 'butter' | 'sage' | 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function LoadingIndicator({ children = 'Loading…' }: { children?: ReactNode }) {
  return <p role="status" className="loading"><span className="spinner" aria-hidden="true" />{children}</p>
}

export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-sprout" aria-hidden="true">✧</span><h3>{title}</h3><p className="muted">{children}</p>{action}</div>
}

export function ErrorNotice({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="error-notice" role="alert"><p>{children}</p>{action}</div>
}

export function PageHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return <div className="page-heading"><Badge>{eyebrow}</Badge><h1>{title}</h1><p className="muted">{children}</p></div>
}

export function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`container ${className}`}>{children}</div>
}
