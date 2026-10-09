import type { SVGProps } from 'react'

export type IconName = 'home' | 'quests' | 'journey' | 'progress' | 'settings' | 'check' | 'lock' | 'sprout'

const paths: Record<IconName, string> = {
  home: 'M3 10 12 3l9 7M5 9v12h14V9M9 21v-7h6v7',
  quests: 'M8 5H5v16h14V5h-3M9 3h6v4H9zM8 12h8M8 16h5',
  journey: 'M5 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM19 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM7 20h8a4 4 0 0 0 0-8H9a4 4 0 0 1 0-8h8',
  progress: 'M4 21V11h4v10M10 21V7h4v14M16 21V3h4v18',
  settings: 'M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1M16 12a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z',
  check: 'm5 12 4 4L19 6',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v12H5zM12 15v3',
  sprout: 'M12 21v-9M12 15C4 15 3 10 3 5c6 0 9 3 9 10ZM12 12c0-7 4-9 9-9 0 6-3 9-9 9Z',
}

// Original outline icons; bundled source, no external icon runtime.
export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg {...props} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
