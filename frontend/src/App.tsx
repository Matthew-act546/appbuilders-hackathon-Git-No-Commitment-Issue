import { Link, Route, Routes } from 'react-router'
import Home from './pages/Home'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="*" element={<main className="mx-auto max-w-xl px-6 py-20"><h1 className="text-3xl font-semibold">Page not found</h1><Link to="/" className="mt-4 inline-block text-teal-700 underline">Return home</Link></main>} />
    </Routes>
  )
}
