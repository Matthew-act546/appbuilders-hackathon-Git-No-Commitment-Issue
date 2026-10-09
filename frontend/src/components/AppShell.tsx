import { useEffect, useRef } from 'react'
import { Link, NavLink, Outlet, useLocation, useOutletContext } from 'react-router'
import { useConnectivity } from '../hooks/useConnectivity'
import { useProfile } from '../hooks/useProfile'
import { useServiceStatus } from '../hooks/useServiceStatus'
import { Icon } from './Icon'
import type { IconName } from './Icon'
import { Sprout } from './Sprout'
import { StatusCard } from './StatusCard'
import { LocalAITest } from './LocalAITest'
import { Badge, Button, Container } from './UI'

const navigation: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'Home', icon: 'home' },
  { to: '/questlines', label: 'My Quests', icon: 'quests' },
  { to: '/journey', label: 'Journey', icon: 'journey' },
  { to: '/progress', label: 'Progress', icon: 'progress' },
]

type ShellContext = ReturnType<typeof useProfile>
export const useAppProfile = () => useOutletContext<ShellContext>()

export function AppShell() {
  const online = useConnectivity()
  const status = useServiceStatus(online)
  const profileState = useProfile(online)
  const { profile, loading } = profileState
  const dialog = useRef<HTMLDialogElement>(null)
  const main = useRef<HTMLElement>(null)
  const location = useLocation()
  const previousPath = useRef(location.pathname)

  useEffect(() => {
    const page = navigation.find(item => item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to))
    document.title = `${page?.label ?? 'Page not found'} · Local AI Quest Companion`
    if (previousPath.current !== location.pathname) {
      main.current?.focus({ preventScroll: true })
      window.scrollTo(0, 0)
      previousPath.current = location.pathname
    }
  }, [location.pathname])

  function refresh() {
    status.refresh()
    profileState.refresh()
  }

  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="app-header">
      <Container className="header-inner">
        <Link to="/" className="brand" aria-label="Local AI Quest Companion — Home"><Sprout small /><span><strong>Local AI</strong><span>Quest Companion</span></span></Link>
        <nav aria-label="Primary navigation" className="navigation">
          {navigation.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`}><Icon name={item.icon} />{item.label}</NavLink>)}
        </nav>
        <div className="header-tools">
          <div className="profile-chips" aria-live="polite">
            {profile ? <><Badge>Level {profile.level}</Badge><span className="xp-total">{profile.total_xp.toLocaleString()} XP</span></> : <span className="helper muted">{loading ? 'Loading progress…' : 'Progress unavailable'}</span>}
          </div>
          <Button variant="quiet" className="icon-button" aria-label="Open local service status and settings" onClick={() => dialog.current?.showModal()}><Icon name="settings" /></Button>
        </div>
      </Container>
    </header>
    <main id="main" ref={main} tabIndex={-1} className="app-main"><Container><Outlet context={profileState satisfies ShellContext} /></Container></main>
    <footer className="app-footer"><Container><Icon name="sprout" /><p>Made for small steps. Powered locally.<span className="footer-note">Keep the frontend, FastAPI and Ollama running on this laptop. Reloading needs the local frontend server.</span></p><button className="text-button" onClick={() => dialog.current?.showModal()}>Local service status</button></Container></footer>
    <dialog ref={dialog} className="status-dialog" aria-labelledby="status-title">
      <div className="dialog-heading"><div><p className="eyebrow">On this laptop</p><h2 id="status-title">Local services & settings</h2></div><Button variant="secondary" onClick={() => dialog.current?.close()}>Close</Button></div>
      <p className="muted">Browser connectivity, backend availability and AI readiness are separate. An offline browser signal does not block local requests.</p>
      <div className="status-grid" aria-live="polite" aria-busy={status.checking}>
        <StatusCard title="Browser connectivity" label={online ? 'Online signal' : 'Offline signal'} available={online} description="A browser signal; it does not confirm internet access or local service availability." />
        <StatusCard title="Backend" label={status.backend === null ? 'Checking…' : status.backend ? 'Connected' : 'Unavailable'} available={status.backend} description={status.backendMessage} />
        <StatusCard title="Local AI" label={status.ai ? status.ai.available ? 'Model ready' : status.ai.server_available ? 'Model unavailable' : 'Ollama unavailable' : status.aiError ? 'Status unavailable' : 'Checking…'} available={status.ai?.available ?? (status.aiError ? false : null)} description={status.ai ? `${status.ai.model} · ${status.ai.message}` : status.aiError ?? 'Checking Ollama and the configured model…'} />
      </div>
      <Button variant="secondary" onClick={refresh} loading={status.checking || loading}>{status.checking || loading ? 'Checking…' : 'Refresh status & progress'}</Button>
      <p className="muted helper settings-note">Model selection and service URLs use the existing local environment configuration. Change the backend model setting and restart FastAPI to switch models manually.</p>
      <LocalAITest onComplete={status.refresh} />
    </dialog>
  </>
}
