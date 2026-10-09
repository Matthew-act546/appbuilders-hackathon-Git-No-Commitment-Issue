import { Link, Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { PageHeading } from './components/UI'
import Home from './pages/Home'
import MyQuests from './pages/MyQuests'
import Journey from './pages/Journey'
import Progress from './pages/Progress'

export default function App() {
  return <Routes>
    <Route element={<AppShell />}>
      <Route path="/" element={<Home />} />
      <Route path="/questlines" element={<MyQuests />} />
      <Route path="/questlines/:id" element={<MyQuests />} />
      <Route path="/journey" element={<Journey />} />
      <Route path="/journey/:id" element={<Journey />} />
      <Route path="/progress" element={<Progress />} />
      <Route path="*" element={<><PageHeading eyebrow="A different path" title="Page not found">This page isn’t part of your companion.</PageHeading><Link to="/" className="text-link">Return home</Link></>} />
    </Route>
  </Routes>
}
