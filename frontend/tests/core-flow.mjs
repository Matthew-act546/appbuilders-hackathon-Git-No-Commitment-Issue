// Real React + FastAPI + temporary SQLite; Ollama is mocked unless --live-ai.
// Run from frontend/: node tests/core-flow.mjs (Chromium and backend/.venv required).
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomUUID } from 'node:crypto'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const temp = await mkdtemp(join(tmpdir(), 'quest-phase4b-'))
const modeFile = join(temp, 'mode')
const api = 'http://127.0.0.1:8004'
const origin = 'http://localhost:4184'
const results = [], requests = [], exceptions = [], children = []
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, nonJsonOnce = false, pendingOnce = false, loseGeneration = false, loseCompletion = false, corruptDetail = false, slowDetail = null
let refreshAfterCompletion = false
let savedListFixture = null
let generationGate = null
let listFailureOnce = false, historyFailureOnce = false, reverseHistory = false, historyTextFixture = null
let replanGate = null, loseReplan = false, pendingReplanOnce = false
const specific = 'Write three unit tests for my FastAPI login endpoint'
function start(command, args, cwd, extra = {}) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...extra }, stdio: ['ignore', 'ignore', 'pipe'] })
  child.stderr.on('data', data => { if (data.toString().includes('Traceback') || data.toString().includes('Address already in use')) process.stderr.write(data) })
  children.push(child)
  return child
}
async function until(check, label, timeout = 12000) {
  const end = Date.now() + timeout
  while (Date.now() < end) { if (await check()) return; await pause(100) }
  throw new Error(`Timed out: ${label}`)
}
async function json(path, body, key) {
  const r = await fetch(api + path, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) })
  return { status: r.status, body: await r.json() }
}
function pass(name, evidence) { results.push({ name, result: 'PASS', evidence }); console.log(JSON.stringify(results.at(-1))) }
const mode = value => writeFile(modeFile, value)
try {
  // Refuse occupied test ports rather than accidentally reusing another service.
  for (const url of [api, origin, 'http://127.0.0.1:9229']) {
    let occupied = false
    try { await fetch(url, { signal: AbortSignal.timeout(1000) }); occupied = true } catch {}
    if (occupied) throw new Error(`Test port already in use: ${url}`)
  }
  await mode('valid')
  const python = process.env.QUEST_TEST_PYTHON || join(root, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const launchBackend = () => start(python, ['-m', 'uvicorn', 'backend_fixture:app', '--host', '127.0.0.1', '--port', '8004', '--log-level', 'warning', '--no-access-log'], join(root, 'backend'), {
    PYTHONPATH: [join(root, 'backend'), join(root, 'frontend/tests')].join(process.platform === 'win32' ? ';' : ':'), DATABASE_URL: `sqlite:///${join(temp, 'state.db').replaceAll('\\', '/')}`,
    OLLAMA_MODEL: 'qwen3:1.7b', OLLAMA_BASE_URL: 'http://127.0.0.1:11434', CORS_ORIGINS: JSON.stringify([origin]), QUEST_TEST_MODE_FILE: modeFile,
  })
  let backend = launchBackend()
  await until(async () => { try { return (await json('/api/health')).body.status === 'ok' } catch { return false } }, 'isolated backend')
  start(process.execPath, [join(root, 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--port', '4184'], join(root, 'frontend'))
  await until(async () => { try { return (await fetch(origin)).ok } catch { return false } }, 'production preview')
  start(process.env.CHROMIUM_BINARY || 'chromium', ['--headless=new', '--window-size=1440,1000', '--no-sandbox', '--disable-dev-shm-usage', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9229', `--user-data-dir=${join(temp, 'browser')}`, 'about:blank'], root)
  let tabs
  await until(async () => { try { tabs = await (await fetch('http://127.0.0.1:9229/json')).json(); return tabs.some(t => t.type === 'page') } catch { return false } }, 'Chromium')
  socket = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let sequence = 0
  const pending = new Map()
  function send(method, params = {}) { return new Promise((resolve, reject) => { const id = ++sequence; pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })) }) }
  async function fulfill(requestId, status, body, headers = {}) {
    return send('Fetch.fulfillRequest', { requestId, responseCode: status, responseHeaders: Object.entries({ 'content-type': 'application/json', 'access-control-allow-origin': origin, 'access-control-allow-headers': 'Content-Type, Idempotency-Key', 'access-control-allow-methods': 'GET, POST, OPTIONS', 'access-control-expose-headers': 'Retry-After', ...headers }).map(([name, value]) => ({ name, value })), body: Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)).toString('base64') })
  }
  async function forward(event) {
    const { requestId, request } = event
    const url = new URL(request.url)
    try {
      requests.push({ method: request.method, path: url.pathname, headers: request.headers, body: request.postData, key: request.headers['Idempotency-Key'] ?? request.headers['idempotency-key'] })
      if (request.method === 'GET' && ((listFailureOnce && url.pathname === '/api/questlines') || (historyFailureOnce && /^\/api\/questlines\//.test(url.pathname)))) {
        listFailureOnce = false; historyFailureOnce = false
        await fulfill(requestId, 503, { error: { code: 'STORAGE_UNAVAILABLE', message: 'Fictional storage outage', retryable: true, request_id: randomUUID(), details: null } })
        return
      }
      if (generationGate && request.method === 'POST' && url.pathname === '/api/questlines') await generationGate
      if (replanGate && request.method === 'POST' && url.pathname.endsWith('/replan')) await replanGate
      if (pendingReplanOnce && request.method === 'POST' && url.pathname.endsWith('/replan')) {
        pendingReplanOnce = false
        await fulfill(requestId, 409, { error: { code: 'REQUEST_IN_PROGRESS', message: 'Fictional pending replan', retryable: true, request_id: randomUUID(), details: null } }, { 'retry-after': '1' })
        return
      }
      if (nonJsonOnce && request.method === 'POST' && url.pathname === '/api/questlines') {
        nonJsonOnce = false
        await fulfill(requestId, 502, '<html>RAW_STACK_TRACE_WITH_PRIVATE_INPUT</html>', { 'content-type': 'text/html' })
        return
      }
      if (pendingOnce && request.method === 'POST' && url.pathname === '/api/questlines') {
        pendingOnce = false
        await fulfill(requestId, 409, { error: { code: 'REQUEST_IN_PROGRESS', message: 'Fictional pending fixture', retryable: true, request_id: randomUUID(), details: null } }, { 'retry-after': '1' })
        return
      }
      if (slowDetail && request.method === 'GET' && url.pathname === `/api/questlines/${slowDetail}`) await pause(600)
      const response = await fetch(api + url.pathname + url.search, { method: request.method, headers: request.headers, ...(request.postData ? { body: request.postData } : {}) })
      let body = await response.text()
      if (request.method === 'GET' && /^\/api\/questlines\//.test(url.pathname) && response.ok && (reverseHistory || historyTextFixture)) {
        const detail = JSON.parse(body)
        if (reverseHistory) detail.completed_quests.reverse()
        if (historyTextFixture && detail.completed_quests[0]) detail.completed_quests[0].completion_encouragement = historyTextFixture
        body = JSON.stringify(detail)
      }
      if (savedListFixture && request.method === 'GET' && url.pathname === '/api/questlines' && response.ok) {
        const list = JSON.parse(body)
        body = JSON.stringify({ ...list, items: savedListFixture.slice(list.offset, list.offset + list.limit), has_more: list.offset + list.limit < savedListFixture.length })
      }
      if (refreshAfterCompletion && request.method === 'POST' && url.pathname.endsWith('/complete') && response.ok) {
        refreshAfterCompletion = false
        // The real DB has committed; reload before React receives confirmation.
        await send('Page.reload', { ignoreCache: true })
        try { await send('Fetch.failRequest', { requestId, errorReason: 'Aborted' }) } catch {}
        return
      }
      if (corruptDetail && request.method === 'GET' && /^\/api\/questlines\//.test(url.pathname) && response.ok) body = JSON.stringify({ ...JSON.parse(body), locked_quests: [{ title: 'SECRET_FUTURE' }] })
      if (loseReplan && request.method === 'POST' && url.pathname.endsWith('/replan') && response.ok) {
        loseReplan = false
        await send('Fetch.failRequest', { requestId, errorReason: 'Failed' })
        return
      }
      if ((loseGeneration && request.method === 'POST' && url.pathname === '/api/questlines') || (loseCompletion && request.method === 'POST' && url.pathname.endsWith('/complete'))) {
        loseGeneration = false; loseCompletion = false
        await send('Fetch.failRequest', { requestId, errorReason: 'Failed' })
        return
      }
      await fulfill(requestId, response.status, body, Object.fromEntries([...response.headers].filter(([name]) => !['content-length', 'transfer-encoding', 'content-encoding', 'connection'].includes(name))))
    } catch (cause) {
      // Abandoned reads may have been canceled while a different route mounted.
      try { await send('Fetch.failRequest', { requestId, errorReason: 'Failed' }) } catch {}
    }
  }
  socket.onmessage = event => {
    const m = JSON.parse(event.data)
    if (m.id) { const p = pending.get(m.id); if (p) { pending.delete(m.id); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result) } }
    if (m.method === 'Runtime.exceptionThrown') exceptions.push(m.params.exceptionDetails.text)
    if (m.method === 'Fetch.requestPaused') void forward(m.params)
  }
  async function evaluate(expression) { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text); return r.result.value }
  async function sidebarAligned() {
    return evaluate("(() => { const saved = document.querySelector('.saved-questlines').getBoundingClientRect(); const settings = document.querySelector('.campaign-settings').getBoundingClientRect(); const progress = document.querySelector('.campaign-progress').getBoundingClientRect(); const pace = document.querySelector('.quest-pace').getBoundingClientRect(); const stage = document.querySelector('.campaign-stage').getBoundingClientRect(); return Math.abs(saved.top - settings.top) <= 2 && Math.abs(saved.bottom - progress.bottom) <= 2 && Math.abs(pace.top - stage.top) <= 2 })()")
  }
  async function open(path) { await send('Page.navigate', { url: origin + path }); await until(() => evaluate(`location.pathname === ${JSON.stringify(path.split('?')[0])} && !!document.querySelector('main h1') && document.readyState === 'complete'`), 'page ' + path) }
  async function click(text) {
    const buttons = "(document.querySelector('dialog[open]') ?? document.querySelector('main')).querySelectorAll('button')"
    await until(() => evaluate(`[...${buttons}].some(b => b.textContent === ${JSON.stringify(text)} && !b.disabled)`), 'enabled button ' + text)
    await evaluate(`[...${buttons}].find(b => b.textContent === ${JSON.stringify(text)}).click()`)
  }
  async function completeWithScrollTracking(lastStage, keyboard) {
    assert.equal(await evaluate("!!document.querySelector('dialog[open]')"), false, 'Dismiss the modal before completing another stage')
    const position = await evaluate(`(() => {
      const button = [...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage');
      button.scrollIntoView({ block: 'center' });
      if (${lastStage}) window.scrollTo(0, document.documentElement.scrollHeight - innerHeight);
      const rect = button.getBoundingClientRect();
      window.completionScrollFrames = [];
      window.trackCompletionScroll = true;
      const sample = () => { window.completionScrollFrames.push({ y: scrollY, height: document.documentElement.scrollHeight, celebration: !!document.querySelector('[data-completion-celebration]') }); if (window.trackCompletionScroll) requestAnimationFrame(sample) };
      requestAnimationFrame(sample);
      return { scrollY, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    })()`)
    assert.ok(position.y > 0 && position.y < 1000, 'Completion button is visible before the real mouse click')
    if (keyboard) {
      await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage').focus({ preventScroll: true })")
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
    } else {
      await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: position.x, y: position.y, button: 'left', clickCount: 1 })
      await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: position.x, y: position.y, button: 'left', clickCount: 1 })
    }
    return position.scrollY
  }
  async function input(id, value) {
    await evaluate(`document.getElementById(${JSON.stringify(id)}).focus()`)
    await send('Input.insertText', { text: value })
    await until(() => evaluate(`document.getElementById(${JSON.stringify(id)}).value === ${JSON.stringify(value)}`), 'input ' + id)
  }
  async function energy(value = 'low') { await evaluate(`const e = document.getElementById('energy'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e, ${JSON.stringify(value)}); e.dispatchEvent(new Event('change',{bubbles:true}))`) }
  async function replaceInput(id, value) {
    await evaluate(`(() => { const field = document.getElementById(${JSON.stringify(id)}); const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(prototype, 'value').set.call(field, ${JSON.stringify(value)}); field.dispatchEvent(new Event('input', { bubbles: true })); field.dispatchEvent(new Event('change', { bubbles: true })) })()`)
  }
  async function replanEnergy(value) { await evaluate(`(() => { const select = document.getElementById('replan-energy'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(select, ${JSON.stringify(value)}); select.dispatchEvent(new Event('change', { bubbles: true })) })()`) }
  async function startCheckIn(goal = specific, details = false, minutes = '20', energyValue = 'low') {
    await open('/')
    await until(() => evaluate("!!document.querySelector('#goal') && !document.querySelector('#goal').disabled"), 'check-in form')
    await input('goal', goal); await input('minutes', minutes); await energy(energyValue)
    if (details) {
      await input('notes', 'Fictional local test context. Use existing files.')
      await evaluate("(() => { const control = document.getElementById('deadline'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(control, '2026-10-10T08:00'); control.dispatchEvent(new Event('input', { bubbles: true })); control.dispatchEvent(new Event('change', { bubbles: true })) })()")
    }
    await click('Start my journey')
    await until(() => evaluate("location.search.includes('check_in=') && !document.querySelector('.loading')"), 'saved check-in')
    return await evaluate("new URLSearchParams(location.search).get('check_in')")
  }
  async function screenshot(name, viewport = false) { const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: !viewport }); await writeFile(join(temp, name + '.png'), Buffer.from(r.data, 'base64')) }
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable')
  await send('Fetch.enable', { patterns: [{ urlPattern: '*://*/api/*', requestStage: 'Request' }] })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  // Opera GX also needs the real window to cover the emulated pointer coordinates.
  const browserWindow = await send('Browser.getWindowForTarget')
  await send('Browser.setWindowBounds', { windowId: browserWindow.windowId, bounds: { width: 1440, height: 1000 } })

  listFailureOnce = true
  await open('/journey')
  await until(() => evaluate("document.querySelector('.journey-picker [role=alert]')?.textContent.includes('Local storage is unavailable')"), 'Journey list failure')
  await click('Retry saved list')
  await until(() => evaluate("document.querySelector('.journey-picker').textContent.includes('A fresh starting point') && !document.querySelector('.journey-picker .loading')"), 'empty Journey recovery')
  assert.equal(await evaluate("document.querySelector('#journey-questline').disabled && !document.querySelector('[data-completed-stage]')"), true)
  assert.equal(requests.some(request => request.method === 'POST'), false)
  pass('Journey empty state and saved-list recovery', 'Empty local storage shows a check-in link and no invented stages; a sanitized storage error recovers through explicit retry; history browsing sends no writes')

  const checkId = await startCheckIn(specific, true)
  assert.equal((await json(`/api/check-in/${checkId}`)).body.status, 'ready')
  const startRequest = requests.find(r => r.method === 'POST' && r.path === '/api/check-in')
  const submitted = JSON.parse(startRequest.body)
  assert.equal(submitted.mode, 'start'); assert.ok(startRequest.key)
  assert.equal(submitted.available_minutes, 20); assert.equal(submitted.energy, 'low')
  assert.equal(submitted.contextual_notes, 'Fictional local test context. Use existing files.')
  assert.equal(submitted.deadline, await evaluate("new Date('2026-10-10T08:00').toISOString()"))
  assert.equal(Date.parse((await json(`/api/check-in/${checkId}`)).body.context.deadline), Date.parse(submitted.deadline))
  await screenshot('ready-check-in')
  pass('Specific check-in and explicit readiness', 'Actual API stores context; no unnecessary question; generation requires its own button')
  await mode('slow')
  let releaseGeneration
  generationGate = new Promise(resolve => { releaseGeneration = resolve })
  await click('Generate My Quests')
  await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent.includes('Generating quests locally')).click()")
  await until(() => evaluate("document.querySelector('[data-generation-loading]')?.matches(':modal')"), 'generation loading popup')
  assert.equal(await evaluate("document.body.style.overflow === 'hidden' && document.activeElement.id === 'generation-heading' && document.querySelector('[data-generation-loading]').dataset.energy === 'low'"), true)
  const loadingBounds = await evaluate("(() => { const popup = document.querySelector('[data-generation-loading]'); const bounds = popup.getBoundingClientRect(); return { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2, width: innerWidth, height: innerHeight, blur: getComputedStyle(popup, '::backdrop').backdropFilter } })()")
  assert.ok(Math.abs(loadingBounds.x - loadingBounds.width / 2) <= 10 && Math.abs(loadingBounds.y - loadingBounds.height / 2) <= 2 && loadingBounds.blur.includes('blur'))
  const firstQuote = await evaluate("document.querySelector('[data-generation-quote]').textContent")
  await click('Another encouragement')
  const secondQuote = await evaluate("document.querySelector('[data-generation-quote]').textContent")
  assert.notEqual(firstQuote, secondQuote)
  await until(() => evaluate(`document.querySelector('[data-generation-quote]').textContent !== ${JSON.stringify(secondQuote)}`), 'automatic encouragement rotation', 15000)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  assert.equal(await evaluate("document.querySelector('[data-generation-loading]').matches(':modal')"), true, 'Pending generation stays visible until the request finishes')
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  assert.equal(await evaluate("!!document.activeElement.closest('[data-generation-loading]')"), true)
  await screenshot('generation-loading-desktop', true)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 780, deviceScaleFactor: 1, mobile: false })
  assert.equal(await evaluate("(() => { const bounds = document.querySelector('[data-generation-loading]').getBoundingClientRect(); return bounds.left >= 0 && bounds.right <= innerWidth && bounds.top >= 0 && bounds.bottom <= innerHeight && document.documentElement.scrollWidth <= innerWidth })()"), true)
  await screenshot('generation-loading-narrow', true)
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  releaseGeneration()
  generationGate = null
  await until(() => evaluate("location.pathname.startsWith('/questlines/') && document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint'"), 'saved questline navigation')
  assert.equal(await evaluate("!document.querySelector('[data-generation-loading]') && document.body.style.overflow !== 'hidden'"), true)
  pass('Energy-aware generation loading popup', 'Centered blurred modal, low-energy encouragement, manual and timed quote changes without extra generation requests, keyboard containment, narrow layout and automatic success dismissal')
  const lineId = await evaluate("location.pathname.split('/').at(-1)")
  assert.equal(requests.filter(r => r.method === 'POST' && r.path === '/api/questlines').length, 1)
  let saved = (await json(`/api/questlines/${lineId}`)).body
  const firstId = saved.current_quest.id
  assert.equal(saved.progress.total_count, 3)
  assert.equal(await evaluate("document.body.innerText.includes('Write the tests') || document.body.innerText.includes('Run the tests')"), false)
  assert.equal(JSON.stringify(saved).includes('Run the tests'), false)
  assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), saved.progress.total_count)
  assert.equal(await evaluate("document.querySelectorAll('.stage-locked').length"), 2)
  assert.equal(await evaluate("document.querySelectorAll('.stage-objectives input').length"), 2)
  assert.equal(await evaluate("document.querySelector('[data-campaign-xp]').textContent"), '0 XP')
  assert.equal(await evaluate("document.body.innerText.includes('YOUR ADAPTIVE QUEST SETTINGS') && document.body.innerText.includes('CAMPAIGN MAP') && document.body.innerText.includes('CAMPAIGN PROGRESS')"), true)
  await evaluate("document.querySelector('.stage-objectives input').focus()")
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await until(() => evaluate("document.querySelector('.stage-objectives input').checked"), 'keyboard checklist')
  assert.equal((await json(`/api/questlines/${lineId}`)).body.revision, saved.revision)
  assert.equal((await json('/api/profile')).body.total_xp, 0)
  pass('Campaign map and keyboard checklist', 'Three backend-counted stages, two source-derived objectives, anonymous locked placeholders; keyboard checks do not mutate progress or XP')
  await mode('valid'); await screenshot('first-quest')
  pass('Generate → save → dashboard, duplicate-click guard and visibility', 'Real questline transaction, safe current DTO, one generation POST; locked titles absent from response and DOM')

  await open(`/journey/${lineId}`)
  await until(() => evaluate("document.querySelector('.journey-empty')?.textContent.includes('Your journey starts with one small step')"), 'questline without completed stages')
  assert.equal(await evaluate("document.querySelector('[data-journey-xp]').textContent === '0 XP' && !document.querySelector('[data-completed-stage]') && !document.querySelector('.journey-history').textContent.includes('Inspect the endpoint')"), true)
  await evaluate(`document.querySelector('.journey-summary a[href="/questlines/${lineId}"]').click()`)
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint' && !document.querySelector('.saved-questlines .loading')"), 'return from empty timeline')
  pass('Journey before the first completion', 'A saved but unfinished questline shows zero earned XP and a supportive empty state; current-stage details stay in My Quests; continue opens the correct questline')

  const summary = (await json('/api/questlines')).body.items[0]
  savedListFixture = [summary, ...Array.from({ length: 27 }, (_, index) => ({ ...summary, id: randomUUID(), goal: `Fictional saved goal ${index + 2}: review the existing local notes and record the useful next step for this campaign.` }))]
  await click('Refresh list')
  await until(() => evaluate("document.querySelectorAll('.questline-link').length === 20 && !document.querySelector('.saved-questlines .loading')"), 'long saved list')
  await evaluate('window.scrollTo(0, 0)')
  await until(sidebarAligned, 'saved-list borders align with settings/progress and pace aligns with Stage 1')
  await pause(200)
  const listBounds = await evaluate("(() => { const list = document.querySelector('.saved-questlines-scroll'); const rect = list.getBoundingClientRect(); return { scrollable: list.scrollHeight > list.clientHeight, y: scrollY, x: rect.left + rect.width / 2, top: rect.top + 30 } })()")
  assert.equal(listBounds.scrollable, true)
  assert.equal(await evaluate(`document.elementFromPoint(${listBounds.x}, ${listBounds.top})?.closest('.saved-questlines-scroll') !== null`), true, 'Wheel coordinates point inside the saved list')
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: listBounds.x, y: listBounds.top })
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: listBounds.x, y: listBounds.top, deltaX: 0, deltaY: 400 })
  await until(() => evaluate("document.querySelector('.saved-questlines-scroll').scrollTop > 0"), 'wheel scrolls saved list')
  assert.equal(await evaluate('scrollY'), listBounds.y, 'Scrolling saved work keeps the campaign in place')
  await evaluate("const list = document.querySelector('.saved-questlines-scroll'); list.scrollTop = 0; list.focus({ preventScroll: true })")
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'PageDown', code: 'PageDown', windowsVirtualKeyCode: 34 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'PageDown', code: 'PageDown', windowsVirtualKeyCode: 34 })
  await until(() => evaluate("document.querySelector('.saved-questlines-scroll').scrollTop > 0"), 'keyboard scrolls saved list')
  await screenshot('saved-questlines-scroll-desktop', true)
  await click('Next')
  await until(() => evaluate("document.querySelectorAll('.questline-link').length === 8"), 'saved-list next page')
  await click('Previous')
  await until(() => evaluate("document.querySelectorAll('.questline-link').length === 20"), 'saved-list previous page')
  await send('Emulation.setDeviceMetricsOverride', { width: 1100, height: 1000, deviceScaleFactor: 1, mobile: false })
  await until(sidebarAligned, 'sidebar alignment follows the resized campaign')
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 1000, deviceScaleFactor: 1, mobile: false })
  assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth && document.querySelector('.saved-questlines').getBoundingClientRect().height <= 512 && document.querySelector('.saved-questlines-scroll').scrollHeight > document.querySelector('.saved-questlines-scroll').clientHeight"), true)
  await screenshot('saved-questlines-scroll-narrow')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  savedListFixture = null
  await click('Refresh list')
  await until(() => evaluate("document.querySelectorAll('.questline-link').length === 1"), 'real saved list restored')
  assert.equal(await evaluate("document.querySelector('.brand strong').textContent === 'Sibol' && document.title === 'My Quests · Sibol'"), true)
  pass('Bounded saved questlines and Sibol branding', '28 fictional summaries: saved-list borders align with Settings and Progress, pace aligns with Stage 1, wheel/keyboard scrolling and pagination stay usable, resize/narrow layouts fit, and app branding reads Sibol')

  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint'"), 'refresh restoration')
  assert.equal(await evaluate("[...document.querySelectorAll('.stage-objectives input')].some(i => i.checked)"), false)
  await click('Pause questline')
  await until(() => evaluate("[...document.querySelectorAll('main button')].some(b => b.textContent === 'Resume questline')"), 'pause committed')
  assert.equal(await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage').disabled"), true)
  assert.equal((await json(`/api/questlines/${lineId}`)).body.current_quest.id, firstId)
  await until(sidebarAligned, 'sidebar alignment after pausing')
  await click('Resume questline')
  await until(() => evaluate("[...document.querySelectorAll('main button')].some(b => b.textContent === 'Pause questline')"), 'resume committed')
  assert.equal((await json('/api/profile')).body.total_xp, 0)
  await until(sidebarAligned, 'sidebar alignment after resuming')
  pass('Refresh, pause and resume persistence', 'Same current quest and 0 XP restored; completion disabled while paused')

  loseCompletion = true
  await click('Complete stage')
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Write the tests' && document.body.innerText.includes('Retry previous action')"), 'lost completion recovery')
  assert.equal((await json('/api/profile')).body.total_xp, 10)
  assert.equal(await evaluate("!!document.querySelector('[data-completion-celebration]')"), false)
  await click('Retry previous action')
  await until(() => evaluate("document.body.innerText.includes('Already completed. No additional XP awarded.')"), 'same quest completion replay')
  assert.equal((await json('/api/profile')).body.total_xp, 10)
  await until(() => evaluate("document.activeElement?.id === 'completion-heading'"), 'celebration keyboard focus')
  const firstMessage = (await json(`/api/questlines/${lineId}`)).body.completed_quests[0].completion_encouragement
  assert.equal(await evaluate("document.querySelector('[data-completion-message]').textContent"), firstMessage)
  assert.equal(await evaluate("document.querySelector('[data-completion-celebration]').textContent.includes('0 additional XP')"), true)
  assert.equal((await json(`/api/questlines/${lineId}`)).body.current_quest.completion_encouragement, null)
  const modal = await evaluate("(() => { const dialog = document.querySelector('.completion-dialog'); const rect = dialog.getBoundingClientRect(); return { modal: dialog.matches(':modal'), blur: getComputedStyle(dialog, '::backdrop').backdropFilter, centerX: rect.x + rect.width / 2, centerY: rect.y + rect.height / 2, width: innerWidth, height: innerHeight, scrollY, locked: document.body.style.overflow === 'hidden' } })()")
  assert.equal(modal.modal, true)
  assert.equal(modal.locked, true)
  assert.ok(modal.blur.includes('blur'))
  assert.ok(Math.abs(modal.centerX - modal.width / 2) <= 10 && Math.abs(modal.centerY - modal.height / 2) <= 2, 'Completion popup is centered in the viewport')
  await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage').focus()")
  assert.equal(await evaluate("document.activeElement.closest('.completion-dialog') !== null"), true, 'Background controls cannot take focus')
  for (let index = 0; index < 3; index++) {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
    assert.equal(await evaluate("document.activeElement.closest('.completion-dialog') !== null"), true, 'Tab stays inside the completion popup')
  }
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 10, y: 10, deltaX: 0, deltaY: 350 })
  await pause(100)
  assert.equal(await evaluate('scrollY'), modal.scrollY, 'The background cannot scroll while the popup is open')
  await screenshot('completion-popup-desktop', true)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 780, deviceScaleFactor: 1, mobile: false })
  const narrowModal = await evaluate("(() => { const rect = document.querySelector('.completion-dialog').getBoundingClientRect(); const close = document.querySelector('.completion-close').getBoundingClientRect(); return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, closeTop: close.top, closeRight: close.right, width: innerWidth, height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth } })()")
  assert.equal(narrowModal.overflow, false)
  assert.ok(narrowModal.left >= 0 && narrowModal.right <= narrowModal.width && narrowModal.top >= 0 && narrowModal.bottom <= narrowModal.height, 'Narrow popup fits within the viewport')
  assert.ok(narrowModal.closeTop >= 0 && narrowModal.closeRight <= narrowModal.width, 'Narrow popup close button stays visible')
  await screenshot('completion-popup-narrow', true)
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await click('Continue Journey')
  assert.equal(await evaluate("document.activeElement?.id"), `campaign-map-${lineId}`)
  assert.equal(await evaluate("document.body.style.overflow"), '')
  pass('Centered completion modal and background isolation', 'Native top-layer dialog, blurred backdrop, focus containment, background scroll lock and restored dashboard interaction')
  pass('Completion celebration, response-loss recovery and keyboard continuation', 'No celebration before confirmed response; replay shows the completed quest’s own message and zero additional XP; focus moves to the heading then Campaign Map; next-stage copy stays private')
  const completions = requests.filter(r => r.method === 'POST' && r.path.endsWith('/complete'))
  assert.equal(completions[0].path, completions[1].path)
  assert.equal(completions[0].body, completions[1].body)
  assert.equal(await evaluate("document.body.innerText.includes('Run the tests')"), false)
  await until(() => evaluate("document.querySelector('.xp-total')?.textContent === '10 XP'"), 'confirmed XP')
  assert.equal(await evaluate("document.querySelector('[data-campaign-xp]').textContent"), '10 XP')
  assert.equal(await evaluate("document.querySelectorAll('.stage-locked').length"), 1)
  pass('Completion, unlocking, lost-response replay and XP', 'Backend awards 10 XP once; retry uses original quest ID/body; only next quest appears after commit')

  saved = (await json(`/api/questlines/${lineId}`)).body
  const paused = await json(`/api/questlines/${lineId}/pause`, { expected_revision: saved.revision }, randomUUID())
  await json(`/api/questlines/${lineId}/resume`, { expected_revision: paused.body.revision }, randomUUID())
  await click('Complete stage')
  await until(() => evaluate("document.body.innerText.includes('This saved state changed') && !document.querySelector('.loading')"), 'stale revision reload')
  assert.equal((await json('/api/profile')).body.total_xp, 10)
  await click('Continue with refreshed state')
  await click('Complete stage')
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Run the tests'"), 'fresh revision completion')
  assert.equal((await json('/api/profile')).body.total_xp, 30)
  await until(() => evaluate("!!document.querySelector('[data-completion-message]')"), 'second celebration')
  const secondMessage = await evaluate("document.querySelector('[data-completion-message]').textContent")
  assert.notEqual(secondMessage, firstMessage)
  assert.ok(secondMessage.includes('Write the tests'))
  assert.equal(await evaluate("document.querySelector('[data-completion-celebration]').textContent.includes('+20 XP awarded') && document.querySelector('[data-completion-celebration]').textContent.includes('Stage 3 unlocked.')"), true)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await until(() => evaluate("!document.querySelector('.completion-dialog') && document.body.style.overflow !== 'hidden'"), 'Escape closes the completion popup')
  assert.equal(await evaluate('document.activeElement?.id'), `campaign-map-${lineId}`)
  pass('Escape dismissal restores normal operations', 'Escape removes the backdrop and scroll lock, restores map focus, and allows the next stage to complete')
  await click('Complete stage')
  await until(() => evaluate("document.body.innerText.includes('Questline completed') && !document.querySelector('.quest-title')"), 'final completion')
  assert.equal((await json('/api/profile')).body.total_xp, 40)
  await until(() => evaluate("document.querySelector('[data-completion-message]')?.textContent.includes('Run the tests')"), 'specific fallback celebration')
  assert.equal(await evaluate("document.querySelector('[data-completion-celebration]').textContent.includes('+10 XP awarded') && document.querySelector('[data-completion-celebration]').textContent.includes('Campaign completed.')"), true)
  await screenshot('completion-celebration')
  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelectorAll('[data-history-encouragement]').length === 3"), 'completion encouragement history refresh')
  assert.equal(await evaluate("!!document.querySelector('[data-completion-celebration]')"), false)
  pass('Distinct encouragement, missing-copy fallback and final refresh', 'Confirmed +20/+10 XP, next-stage number only, own-title messages, final campaign status; three completed-history messages persist without replaying celebration or rewards')
  pass('Stale revision recovery and final completion', 'Conflict reloads canonical revision without XP; explicit fresh completion unlocks final quest, then completes line; total 40 XP')

  const finishedHistory = (await json(`/api/questlines/${lineId}`)).body
  const historyWriteCount = requests.filter(request => request.method === 'POST').length
  reverseHistory = true
  await open(`/journey/${lineId}`)
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 3 && !!document.querySelector('[data-journey-finished]')"), 'completed-stage timeline')
  const chronological = [...finishedHistory.completed_quests].sort((a, b) => Date.parse(a.completed_at) - Date.parse(b.completed_at) || a.order - b.order)
  assert.deepEqual(await evaluate("[...document.querySelectorAll('[data-completed-stage]')].map(stage => stage.dataset.completedStage)"), chronological.map(quest => quest.id))
  assert.deepEqual(await evaluate("[...document.querySelectorAll('.stage-memory time')].map(time => time.dateTime)"), chronological.map(quest => quest.completed_at))
  assert.equal(await evaluate("document.querySelector('[data-journey-xp]').textContent"), '40 XP')
  assert.equal(await evaluate("document.querySelectorAll('[data-journey-encouragement]').length === 3 && document.querySelectorAll('.stage-memory-details:not([open])').length === 3 && !document.querySelector('.stage-locked')"), true)
  assert.equal(await evaluate("document.querySelector('[data-journey-finished]').textContent.includes('all 3 stages') && document.querySelector('[data-journey-finished]').textContent.includes('40 XP')"), true)
  await evaluate("document.querySelector('.stage-memory-details summary').focus()")
  assert.equal(await evaluate("document.activeElement === document.querySelector('.stage-memory-details summary')"), true)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await until(() => evaluate("document.querySelector('.stage-memory-details').open"), 'keyboard expands saved stage')
  assert.equal(await evaluate(`document.querySelector('.stage-memory-details').textContent.includes(${JSON.stringify(chronological[0].action)}) && document.querySelector('.stage-memory-details').textContent.includes(${JSON.stringify(chronological[0].completion_criteria)})`), true)
  await evaluate('window.scrollTo(0, 0)')
  await screenshot('journey-timeline-desktop')
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 1000, deviceScaleFactor: 1, mobile: false })
  assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('.stage-memory, .journey-picker')].every(card => card.getBoundingClientRect().left >= 0 && card.getBoundingClientRect().right <= innerWidth)"), true)
  await screenshot('journey-timeline-narrow')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await click('Refresh history')
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 3 && !document.querySelector('.loading')"), 'timeline explicit refresh')
  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 3 && !!document.querySelector('[data-journey-finished]')"), 'timeline refresh persistence')
  reverseHistory = false
  assert.equal(requests.filter(request => request.method === 'POST').length, historyWriteCount)
  assert.equal((await json('/api/profile')).body.total_xp, 40)
  assert.deepEqual((await json(`/api/questlines/${lineId}`)).body, finishedHistory)
  pass('Completed-stage timeline, keyboard details and refresh persistence', 'Actual completed SQLite records render chronologically despite reversed response order, with exact timestamps and 40 earned XP; native details expand by keyboard; completion summary and desktop/narrow layouts fit; viewing and refreshing award no XP')

  historyFailureOnce = true
  await click('Refresh history')
  await until(() => evaluate("document.querySelector('[role=alert]')?.textContent.includes('Local storage is unavailable') && !document.querySelector('[data-completed-stage]')"), 'history read failure clears stale timeline')
  await click('Retry history')
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 3"), 'history retry recovers')
  corruptDetail = true
  await click('Refresh history')
  await until(() => evaluate("document.querySelector('[role=alert]')?.textContent.includes('invalid response')"), 'Journey rejects hidden fields')
  assert.equal(await evaluate("document.body.innerText.includes('SECRET_FUTURE') || !!document.querySelector('[data-completed-stage]')"), false)
  corruptDetail = false
  historyTextFixture = '<img src=x onerror="window.journeyInjected=true">'
  await click('Retry history')
  await until(() => evaluate(`document.querySelector('[data-journey-encouragement]')?.textContent.includes(${JSON.stringify(historyTextFixture)})`), 'saved model text stays plain text')
  assert.equal(await evaluate("!!document.querySelector('.stage-memory img') || window.journeyInjected === true"), false)
  historyTextFixture = null
  await open('/journey/10000000-0000-4000-8000-000000000099')
  await until(() => evaluate("document.querySelector('[role=alert]')?.textContent.includes('no longer available')"), 'Journey missing questline')
  assert.equal(await evaluate("!!document.querySelector('[data-completed-stage]') || document.querySelector('#journey-questline').disabled"), false)
  pass('Journey history failures, safe model text and unknown questline', 'Failed reads clear the timeline and retry restores it; strict DTO validation rejects hidden future fields; HTML-like encouragement renders as text; a missing goal leaves the selector usable')

  const ambiguousId = await startCheckIn('Finish my assignment')
  const question = (await json(`/api/check-in/${ambiguousId}`)).body.question
  await until(() => evaluate("!!document.querySelector('#clarification')"), 'clarification form')
  assert.equal(await evaluate("document.querySelector('.clarification-panel > p').textContent"), question)
  await input('clarification', specific + ' using existing local files.')
  await click('Continue')
  await until(() => evaluate("!!document.querySelector('.ready-panel') && !document.querySelector('#clarification')"), 'clarification saved')
  const ready = (await json(`/api/check-in/${ambiguousId}`)).body
  assert.equal(ready.context.goal, 'Finish my assignment'); assert.equal(ready.revision, 2)
  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelector('.ready-panel')?.textContent.includes('existing local files')"), 'check-in refresh recovery')
  await evaluate("document.querySelector('.brand').click()")
  await until(() => evaluate("!location.search && [...document.querySelectorAll('main button')].some(b => b.textContent === 'Start my journey' && !b.disabled)"), 'Home returns to a new intent')
  assert.equal(await evaluate("document.querySelector('#goal').value"), 'Finish my assignment')
  await open('/?check_in=' + ambiguousId)
  await until(() => evaluate("!!document.querySelector('.ready-panel')"), 'restore saved check-in by opaque ID')
  pass('Actual clarification and check-in refresh', 'Exact server question; original goal/context and answer persist with revision 2; opaque URL ID restores the form')

  for (const [value, expected] of [['unavailable', 'Ollama is unavailable'], ['timeout', 'Local generation timed out'], ['invalid', 'invalid plan'], ['rejected', 'No quests were saved']]) {
    await mode(value)
    const button = await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent.includes('Generate My Quests')).textContent")
    await click(button)
    await until(() => evaluate(`document.querySelector('[role=alert]')?.textContent.includes(${JSON.stringify(expected)})`), value + ' error')
    assert.equal((await json(`/api/check-in/${ambiguousId}`)).body.status, 'ready')
    assert.equal((await json('/api/questlines')).body.items.length, 1)
    assert.equal(await evaluate("!!document.querySelector('.quest-title')"), false)
    assert.equal(await evaluate("!document.querySelector('[data-generation-loading]') && document.body.style.overflow !== 'hidden'"), true, 'Generation errors dismiss the loading popup and restore the form')
  }
  const attempts = requests.filter(r => r.method === 'POST' && r.path === '/api/questlines').slice(1)
  assert.equal(new Set(attempts.map(r => r.key)).size, 1)
  assert.equal(new Set(attempts.map(r => r.body)).size, 1)
  pass('AI unavailable, timeout, invalid output and semantic rejection', 'Actual API error paths using mocked Ollama: context retained, no plan saved or fabricated, same key/body on explicit retries')
  nonJsonOnce = true
  await click('Retry Generate My Quests')
  await until(() => evaluate("document.querySelector('[role=alert]')?.textContent.includes('could not complete this request (502)')"), 'sanitized non-JSON server error')
  assert.equal(await evaluate("document.body.innerText.includes('RAW_STACK_TRACE_WITH_PRIVATE_INPUT')"), false)
  pass('Non-JSON error sanitization', 'Mocked HTML gateway error never exposes traces/private text; check-in remains retryable')
  await mode('valid'); pendingOnce = true
  await click('Retry Generate My Quests')
  await until(() => evaluate("document.body.innerText.includes('Retry in')"), 'pending Retry-After')
  assert.equal(await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent.includes('Generate My Quests')).disabled"), true)
  await until(() => evaluate("[...document.querySelectorAll('main button')].some(b => b.textContent.includes('Generate My Quests') && !b.disabled)"), 'pending wait finished')
  loseGeneration = true
  await click('Retry Generate My Quests')
  await until(() => evaluate("location.pathname.startsWith('/questlines/') && !!document.querySelector('.quest-title')"), 'committed generation lost-response recovery')
  const secondId = await evaluate("location.pathname.split('/').at(-1)")
  assert.equal((await json('/api/questlines')).body.items.length, 2)
  pass('Pending response and lost generation response', 'Mocked 409/Retry-After prevents early retry; actual successful commit with dropped response is recovered through consumed check-in, without duplicate line')

  await mode('unavailable')
  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("!!document.querySelector('.quest-title')"), 'saved work AI-down')
  await click('Pause questline'); await click('Resume questline'); await click('Complete stage')
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Write the tests'"), 'non-AI completion')
  assert.equal((await json('/api/profile')).body.total_xp, 50)
  pass('Saved quests remain usable with AI unavailable', 'Real SQLite list/detail/pause/resume/completion work while the mocked runtime cannot connect; 50 total XP confirmed')

  const writesBeforeJourney = requests.filter(request => request.method === 'POST').length
  await open(`/journey/${secondId}`)
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 1"), 'active campaign history')
  assert.equal(await evaluate("document.querySelector('[data-journey-xp]').textContent === '10 XP' && !document.querySelector('[data-journey-finished]') && !document.querySelector('.journey-history').textContent.includes('Write the tests')"), true)
  await evaluate(`document.querySelector('.journey-summary a[href="/questlines/${secondId}"]').click()`)
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Write the tests'"), 'continue correct saved questline')
  await click('Pause questline')
  await until(() => evaluate("document.querySelector('.quest-pace')?.textContent.includes('Resume questline')"), 'pause before revisiting history')
  await open(`/journey/${secondId}`)
  await until(() => evaluate("document.querySelector('.journey-summary .badge')?.textContent === 'paused' && document.querySelectorAll('[data-completed-stage]').length === 1"), 'paused completed-stage history')
  assert.equal(await evaluate("document.querySelector('.journey-summary').textContent.includes('Return to paused questline') && document.querySelector('[data-journey-xp]').textContent === '10 XP'"), true)
  await evaluate(`document.querySelector('.journey-summary a[href="/questlines/${secondId}"]').click()`)
  await until(() => evaluate("document.querySelector('.quest-pace')?.textContent.includes('Resume questline')"), 'paused return keeps paused state')
  await click('Resume questline')
  await until(() => evaluate("document.querySelector('.quest-pace')?.textContent.includes('Pause questline')"), 'resume after history')
  assert.equal(requests.filter(request => request.method === 'POST').length, writesBeforeJourney + 2, 'Only the explicit pause and resume actions write')
  assert.equal((await json('/api/profile')).body.total_xp, 50)
  pass('Active and paused Journey history without AI', 'Completed stages remain readable during mocked AI outage; current and future details stay absent; campaign XP is 10 while lifetime XP is 50; continue links return to the correct questline without resuming it implicitly')

  const journeySummaries = (await json('/api/questlines')).body.items
  const journeySummary = journeySummaries.find(item => item.id === lineId)
  savedListFixture = [...Array.from({ length: 21 }, (_, index) => ({ ...journeySummary, id: randomUUID(), goal: `Fictional history goal ${index + 1}` })), journeySummary, journeySummaries.find(item => item.id === secondId)]
  await open('/journey')
  await until(() => evaluate("document.querySelector('#journey-questline')?.options.length === 21 && !document.querySelector('.loading')"), 'Journey first selector page')
  await click('Next goals')
  await until(() => evaluate("document.querySelector('#journey-questline')?.options.length === 4 && !document.querySelector('.loading')"), 'Journey second selector page')
  await evaluate(`(() => { const select = document.getElementById('journey-questline'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(select, '${lineId}'); select.dispatchEvent(new Event('change', { bubbles: true })) })()`)
  await until(() => evaluate(`location.pathname === '/journey/${lineId}' && document.querySelectorAll('[data-completed-stage]').length === 3 && !document.querySelector('.loading')`), 'select goal on a later page')
  assert.equal(await evaluate(`document.querySelector('#journey-questline').value === '${lineId}' && document.querySelector('#journey-questline').selectedOptions[0].textContent.includes(${JSON.stringify(finishedHistory.goal)})`), true)
  savedListFixture = null
  await click('Refresh list')
  await until(() => evaluate("document.querySelector('#journey-questline').options.length === 3 && !document.querySelector('.loading')"), 'real Journey selector restored')
  slowDetail = lineId
  await open(`/journey/${lineId}`)
  await evaluate(`window.history.pushState({}, '', '/journey/${secondId}'); window.dispatchEvent(new PopStateEvent('popstate'))`)
  await until(() => evaluate("document.querySelector('.journey-summary .goal-heading')?.textContent === 'Finish my assignment' && document.querySelectorAll('[data-completed-stage]').length === 1"), 'Journey selects another questline during a slow read')
  await pause(800)
  assert.equal(await evaluate("document.querySelector('.journey-summary .goal-heading').textContent"), 'Finish my assignment')
  slowDetail = null
  pass('Journey selector pagination and abandoned reads', 'A goal beyond the first 20 remains selectable and labeled after navigation; a slow previous goal cannot replace the newly selected timeline')

  corruptDetail = true
  await open(`/questlines/${secondId}`)
  await until(() => evaluate("document.body.innerText.includes('invalid response')"), 'unexpected locked field rejected')
  assert.equal(await evaluate("document.body.innerText.includes('SECRET_FUTURE') || !!document.querySelector('.quest-title')"), false)
  corruptDetail = false
  await click('Retry loading'); await until(() => evaluate("!!document.querySelector('.quest-title')"), 'safe response restored')
  pass('Strict public DTO boundary', 'Injected hidden field causes safe rejection; neither hidden content nor a current-quest UI is rendered until a valid response is loaded')

  await open('/questlines/10000000-0000-4000-8000-000000000099')
  await until(() => evaluate("document.body.innerText.includes('no longer available')"), 'unknown questline')
  assert.equal(await evaluate("!!document.querySelector('.quest-title')"), false)
  pass('Stale questline address', 'Actual API 404 offers a return to saved questlines instead of an empty or fabricated dashboard')
  await open(`/questlines/${lineId}`)
  await until(() => evaluate("document.querySelector('[data-campaign-xp]')?.textContent === '40 XP'"), 'completed campaign XP')
  assert.equal((await json('/api/profile')).body.total_xp, 50)
  assert.equal(await evaluate("document.querySelector('.campaign-progress').innerText.includes('Lifetime profile XP') && document.querySelector('.campaign-progress').innerText.includes('50 XP')"), true)
  assert.equal(await evaluate("document.querySelectorAll('.stage-locked').length"), 0)
  pass('Campaign versus lifetime progress', 'Completed campaign shows 40 earned XP while backend profile has 50 across campaigns; no locked stages remain')
  slowDetail = lineId
  await open(`/questlines/${lineId}`)
  await evaluate(`document.querySelector('a[href="/questlines/${secondId}"]')?.click()`)
  // Saved links can still be loading; use normal browser history navigation if needed.
  await evaluate(`window.history.pushState({}, '', '/questlines/${secondId}'); window.dispatchEvent(new PopStateEvent('popstate'))`)
  await until(() => evaluate("document.querySelector('.goal-heading')?.textContent === 'Finish my assignment'"), 'selected route response')
  await pause(800)
  assert.equal(await evaluate("document.querySelector('.goal-heading').textContent"), 'Finish my assignment')
  slowDetail = null
  pass('Abandoned read and selected identity', 'Delayed previous questline cannot replace the newly selected route state')
  for (const width of [1440, 640, 390]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: false })
    assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth'))
  }
  await screenshot('dashboard-narrow')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await screenshot('dashboard-desktop')
  assert.equal(await evaluate('localStorage.length + sessionStorage.length'), 0)
  assert.equal(await evaluate('navigator.serviceWorker.controller'), null)
  assert.equal(exceptions.length, 0)
  pass('Design and privacy regression', 'No horizontal overflow at 1440/640/390px; no private browser storage, service worker or uncaught exceptions')

  for (const count of [2, 6]) {
    await mode(`stages-${count}`)
    await startCheckIn(specific)
    await click('Generate My Quests')
    await until(() => evaluate("location.pathname.startsWith('/questlines/') && !!document.querySelector('.quest-title')"), `saved ${count}-stage line`)
    const id = await evaluate("location.pathname.split('/').at(-1)")
    let sized = (await json(`/api/questlines/${id}`)).body
    const first = sized.current_quest
    const before = (await json('/api/profile')).body.total_xp
    assert.equal(sized.progress.total_count, count)
    assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), count)
    assert.equal(await evaluate("document.querySelectorAll('.stage-objectives input').length"), 3)
    assert.equal(await evaluate("document.body.innerText.includes('Sized stage 2')"), false)
    assert.equal(JSON.stringify(sized).includes('Sized stage 2'), false)
    await screenshot(`sized-${count}-stage-first`)
    const completionScroll = await evaluate("(() => { const button = [...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage'); button.scrollIntoView({ block: 'center' }); button.focus({ preventScroll: true }); return window.scrollY })()")
    assert.ok(completionScroll > 100, 'Complete the stage from a scrolled dashboard')
    await click('Complete stage')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Sized stage 2'"), `unlock second of ${count}`)
    await until(() => evaluate("document.activeElement?.id === 'completion-heading' && !document.querySelector('.loading')"), `completion focus without scrolling for ${count} stages`)
    await pause(150)
    const completedScroll = await evaluate('window.scrollY')
    assert.ok(Math.abs(completedScroll - completionScroll) <= 2, `Completing a stage preserves scroll position in the ${count}-stage campaign (${completionScroll} → ${completedScroll})`)
    const continueScroll = await evaluate('window.scrollY')
    await click('Continue Journey')
    await until(() => evaluate(`!document.querySelector('[data-completion-celebration]') && document.activeElement?.id === 'campaign-map-${id}'`), 'continue focus without scrolling')
    await pause(150)
    const continuedScroll = await evaluate('window.scrollY')
    assert.ok(Math.abs(continuedScroll - continueScroll) <= 2, `Continuing after completion preserves scroll position in the ${count}-stage campaign (${continueScroll} → ${continuedScroll})`)
    pass(`${count}-stage completion scroll position`, 'Completing a scrolled stage and continuing preserve the scroll offset while keeping keyboard focus on the result and Campaign Map')
    const duplicate = await json(`/api/quests/${first.id}/complete`, { expected_revision: 1 })
    assert.equal(duplicate.body.awarded_xp, 0)
    assert.equal((await json('/api/profile')).body.total_xp, before + 10)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Sized stage 2'"), `refresh ${count} stages`)
    assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), count)
    for (let index = 1; index < count; index++) {
      const expectedScroll = await completeWithScrollTracking(index + 1 === count, index % 2 === 0)
      await until(() => evaluate(index + 1 === count ? "document.body.innerText.includes('Campaign completed')" : `document.querySelector('.quest-title')?.textContent === 'Sized stage ${index + 2}'`), `complete sized stage ${index + 1}`)
      await until(() => evaluate("document.activeElement?.id === 'completion-heading' && !document.querySelector('.loading')"), 'real-click completion settled')
      if (index % 2 === 0) await evaluate("document.querySelector('[aria-label=\"Close completion popup\"]').click()")
      else await click('Continue Journey')
      await until(() => evaluate("!document.querySelector('.completion-dialog') && document.body.style.overflow !== 'hidden'"), 'completion popup dismissed without moving the page')
      await pause(150)
      const frames = await evaluate('(() => { window.trackCompletionScroll = false; return window.completionScrollFrames })()')
      const changedFrames = frames.filter((frame, frameIndex) => frameIndex === 0 || frame.y !== frames[frameIndex - 1].y || frame.height !== frames[frameIndex - 1].height)
      assert.ok(frames.every(frame => Math.abs(frame.y - expectedScroll) <= 2), `Real-click stage ${index + 1}/${count} stays scrolled throughout completion: ${JSON.stringify({ expectedScroll, changedFrames })}`)
    }
    sized = (await json(`/api/questlines/${id}`)).body
    assert.equal(sized.status, 'completed')
    assert.equal((await json('/api/profile')).body.total_xp, before + count * 10)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.body.innerText.includes('Campaign completed')"), `completed sized ${count} refresh`)
    assert.equal(await evaluate("document.querySelector('[data-campaign-xp]').textContent"), `${count * 10} XP`)
    pass(`${count}-stage Campaign Map integration`, 'Mocked count selection, real API/SQLite: current-only content, anonymous locked stages, three temporary checkpoints, one-time XP, sequential unlocking and completed refresh persistence')
  }

  const energyQuotes = new Set()
  for (const energyValue of ['medium', 'high']) {
    await mode('unavailable')
    await startCheckIn(specific, false, '20', energyValue)
    generationGate = new Promise(resolve => { releaseGeneration = resolve })
    await click('Generate My Quests')
    await until(() => evaluate(`document.querySelector('[data-generation-loading]')?.dataset.energy === '${energyValue}'`), energyValue + ' loading encouragement')
    const quote = await evaluate("document.querySelector('[data-generation-quote]').textContent")
    assert.ok(quote.length > 20 && !energyQuotes.has(quote))
    energyQuotes.add(quote)
    assert.equal(await evaluate(`document.querySelector('[data-generation-loading]').textContent.includes('${energyValue === 'medium' ? 'A steady pace' : 'Room to focus'}')`), true)
    releaseGeneration()
    generationGate = null
    await until(() => evaluate("!!document.querySelector('[role=alert]') && !document.querySelector('[data-generation-loading]') && document.body.style.overflow !== 'hidden'"), energyValue + ' generation failure restores interaction')
    assert.equal(await evaluate("[...document.querySelectorAll('main button')].some(button => button.textContent === 'Retry Generate My Quests' && !button.disabled)"), true)
  }
  pass('Energy-specific encouragement and error dismissal', 'Medium/high energy use distinct encouragement and tone; unavailable AI closes the popup and leaves the saved check-in ready for an explicit retry')

  const beforeHistoryReplan = (await json(`/api/questlines/${secondId}`)).body
  const xpBeforeHistoryReplan = (await json('/api/profile')).body
  await open(`/journey/${secondId}`)
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 1"), 'history before replan')
  const historyBeforeReplan = await evaluate("document.querySelector('[data-completed-stage]').textContent")
  await mode('stages-2')
  const replannedHistory = await json(`/api/questlines/${secondId}/replan`, { expected_revision: beforeHistoryReplan.revision, available_minutes: 10, energy: 'low', reason: 'Use a smaller session while keeping the completed stage.' }, randomUUID())
  assert.equal(replannedHistory.status, 200)
  assert.deepEqual(replannedHistory.body.completed_quests, beforeHistoryReplan.completed_quests)
  await click('Refresh history')
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 1 && !document.querySelector('.loading')"), 'history after replan')
  assert.equal(await evaluate("document.querySelector('[data-completed-stage]').textContent"), historyBeforeReplan)
  assert.equal(await evaluate("document.querySelector('[data-journey-xp]').textContent === '10 XP' && !document.querySelector('.journey-history').textContent.includes('Sized stage') && !document.querySelector('.journey-history').textContent.includes('Write the tests')"), true)
  assert.deepEqual((await json('/api/profile')).body, xpBeforeHistoryReplan)
  pass('Journey preserves completed stages across replan', 'An actual API replan replaces unfinished work in temporary SQLite; refreshing Journey preserves the completed ID, date, details, encouragement and earned XP while keeping replacement and superseded details hidden')

  await mode('valid')
  const replanCheckIn = await startCheckIn(specific, true, '25', 'medium')
  await click('Generate My Quests')
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint'"), 'replan source campaign')
  const uiReplanId = await evaluate("location.pathname.split('/').at(-1)")
  const replanRequests = () => requests.filter(request => request.method === 'POST' && request.path === `/api/questlines/${uiReplanId}/replan`)
  await click('Complete stage')
  await until(() => evaluate("!!document.querySelector('[data-completion-celebration]')"), 'complete before replan')
  await click('Continue Journey')
  await click('Pause questline')
  await until(() => evaluate("document.querySelector('.replan-panel')?.textContent.includes('Resume this questline before replanning')"), 'paused replan disabled')
  assert.equal(await evaluate("document.querySelector('.replan-panel button').disabled"), true)
  await click('Resume questline')
  await click('Replan remaining stages')
  await until(() => evaluate("document.activeElement?.id === 'replan-minutes'"), 'replan form keyboard focus')
  assert.equal(await evaluate("document.activeElement?.id === 'replan-minutes' && document.querySelector('#replan-minutes').value === '25' && document.querySelector('#replan-energy').value === 'medium'"), true)
  await replaceInput('replan-minutes', '0')
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('.replan-panel [role=alert]')?.textContent.includes('1–1440 whole minutes')"), 'replan field validation')
  assert.equal(replanRequests().length, 0)
  await replaceInput('replan-minutes', '10')
  await replanEnergy('low')
  await replaceInput('replan-reason', 'Use my existing files; I have a shorter session now.')
  await evaluate("document.querySelector('.replan-panel').scrollIntoView({ block: 'center' })")
  await screenshot('replan-form-desktop', true)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 1000, deviceScaleFactor: 1, mobile: false })
  assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth && document.querySelector('.replan-panel form').getBoundingClientRect().right <= innerWidth"), true)
  await screenshot('replan-form-narrow')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  const beforeUIReplan = (await json(`/api/questlines/${uiReplanId}`)).body
  const profileBeforeUIReplan = (await json('/api/profile')).body
  pass('Frontend replan form, validation and paused guard', 'Saved capacity prefills the accessible form; invalid minutes send no request; paused goals cannot replan; desktop/narrow layouts fit')

  for (const [index, value, expected] of [[0, 'unavailable', 'Ollama is unavailable'], [1, 'timeout', 'timed out'], [2, 'invalid', 'invalid plan'], [3, 'rejected', 'quality checks']]) {
    await mode(value)
    await click(index === 0 ? 'Generate revised stages' : 'Retry replanning')
    await until(() => evaluate(`document.querySelector('.replan-feedback [role=alert]')?.textContent.includes(${JSON.stringify(expected)}) && !document.querySelector('[data-generation-loading]')`), 'replan ' + value + ' recovery')
    assert.deepEqual((await json(`/api/questlines/${uiReplanId}`)).body, beforeUIReplan)
    assert.deepEqual((await json('/api/profile')).body, profileBeforeUIReplan)
    assert.equal(await evaluate("document.querySelector('#replan-minutes').value === '10' && document.querySelector('#replan-energy').value === 'low' && document.querySelector('.replan-panel fieldset').disabled && document.activeElement.classList.contains('replan-feedback') && document.body.style.overflow !== 'hidden'"), true)
  }
  assert.equal(new Set(replanRequests().map(request => request.key)).size, 1)
  assert.equal(new Set(replanRequests().map(request => request.body)).size, 1)
  const replanBody = JSON.parse(replanRequests()[0].body)
  assert.equal(replanBody.expected_revision, beforeUIReplan.revision)
  assert.equal(replanBody.available_minutes, 10)
  assert.equal(replanBody.energy, 'low')
  assert.equal('deadline' in replanBody || 'contextual_notes' in replanBody, false)
  pass('Frontend replan failure rollback and unchanged retries', 'Actual API failures for unavailable AI, timeout, malformed output and essential rejection preserve the old plan/history/profile; input is retained and explicit retries reuse one key and body; optional deadline/notes are omitted')

  pendingReplanOnce = true
  await click('Retry replanning')
  await until(() => evaluate("document.querySelector('.replan-feedback')?.textContent.includes('Retry in')"), 'pending replan wait')
  assert.equal(await evaluate("[...document.querySelectorAll('.replan-feedback button')].find(button => button.textContent === 'Retry replanning').disabled && !document.querySelector('.replan-feedback').textContent.includes('Edit replanning details')"), true)
  await mode('replan-single')
  let releaseReplan
  replanGate = new Promise(resolve => { releaseReplan = resolve })
  await click('Retry replanning')
  await until(() => evaluate("document.querySelector('[data-generation-loading]')?.matches(':modal') && document.querySelector('[data-generation-loading]').dataset.energy === 'low'"), 'replan loading popup')
  assert.equal(await evaluate("document.querySelector('[data-generation-loading]').textContent.includes('Making room for your new pace') && [...document.querySelectorAll('.quest-pace button, .quest-actions button')].every(button => button.disabled)"), true)
  const pendingReplanCount = replanRequests().length
  await evaluate("document.querySelector('.replan-panel form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))")
  await pause(150)
  assert.equal(replanRequests().length, pendingReplanCount)
  await screenshot('replan-loading-popup', true)
  releaseReplan(); replanGate = null
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Finish the remaining test work' && !document.querySelector('[data-generation-loading]')"), 'replan saved and revealed')
  const replannedUI = (await json(`/api/questlines/${uiReplanId}`)).body
  assert.equal(replannedUI.plan_version, beforeUIReplan.plan_version + 1)
  assert.equal(replannedUI.progress.total_count, 2)
  assert.equal(replannedUI.progress.remaining_count, 1)
  assert.deepEqual(replannedUI.completed_quests, beforeUIReplan.completed_quests)
  assert.deepEqual((await json('/api/profile')).body, profileBeforeUIReplan)
  assert.equal(replannedUI.deadline, beforeUIReplan.deadline)
  assert.equal(replannedUI.available_minutes, 10)
  assert.equal(replannedUI.energy, 'low')
  assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length === 2 && document.querySelector('[data-campaign-xp]').textContent === '10 XP' && !document.querySelector('.quest-title').textContent.includes('Write the tests') && !document.querySelector('[data-completion-celebration]')"), true)
  await until(() => evaluate(`document.activeElement.id === 'campaign-map-${uiReplanId}'`), 'replan returns focus to map')
  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Finish the remaining test work'"), 'replan refresh persistence')
  assert.equal((await json(`/api/check-in/${replanCheckIn}`)).body.context.contextual_notes, 'Fictional local test context. Use existing files.')
  pass('Frontend replan save, pending guard and one remaining stage', 'Native loading modal blocks concurrent completion/pause and duplicate submissions; confirmed backend version changes the map from three to two total stages, preserves completed records/XP/deadline, applies new capacity and survives refresh')

  await mode('stages-2')
  await click('Replan remaining stages')
  await replaceInput('replan-reason', 'Keep the same goal and make the next session clearer.')
  loseReplan = true
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('.replan-feedback')?.textContent.includes('may have committed') && document.querySelector('.quest-title')?.textContent === 'Sized stage 1' && !document.querySelector('[data-generation-loading]')"), 'lost replan response canonical recovery')
  const afterLostReplan = (await json(`/api/questlines/${uiReplanId}`)).body
  assert.equal(afterLostReplan.plan_version, replannedUI.plan_version + 1)
  assert.equal(await evaluate("document.querySelector('.replan-feedback').textContent.includes('Edit replanning details')"), false)
  await click('Retry replanning')
  await until(() => evaluate("document.querySelector('.success-notice')?.textContent.includes('remaining stages have been replanned') && !document.querySelector('[data-generation-loading]')"), 'lost replan replay')
  assert.deepEqual((await json(`/api/questlines/${uiReplanId}`)).body, afterLostReplan)
  assert.deepEqual((await json('/api/profile')).body, profileBeforeUIReplan)
  const lastReplans = replanRequests().slice(-2)
  assert.equal(lastReplans[0].key, lastReplans[1].key)
  assert.equal(lastReplans[0].body, lastReplans[1].body)
  pass('Frontend replan lost-response replay', 'A real committed replacement with a dropped response reloads canonical state; retry uses the original revision/body/key and returns that same plan without a second version or XP change')

  await click('Replan remaining stages')
  await replaceInput('replan-reason', 'A stale form must not overwrite newer work.')
  const concurrentPause = await json(`/api/questlines/${uiReplanId}/pause`, { expected_revision: afterLostReplan.revision }, randomUUID())
  const concurrentResume = await json(`/api/questlines/${uiReplanId}/resume`, { expected_revision: concurrentPause.body.revision }, randomUUID())
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('.replan-feedback')?.textContent.includes('This saved state changed') && document.querySelector('.replan-feedback').textContent.includes('Continue with refreshed state')"), 'stale replan reload')
  assert.deepEqual((await json(`/api/questlines/${uiReplanId}`)).body, concurrentResume.body)
  assert.equal(await evaluate("document.querySelector('.replan-feedback').textContent.includes('Retry replanning')"), false)
  await click('Continue with refreshed state')
  await click('Replan remaining stages')
  await replaceInput('replan-reason', 'Use a new explanation after the failed request.')
  await mode('invalid')
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('.replan-feedback')?.textContent.includes('invalid plan')"), 'known failed replan before editing')
  const knownFailure = replanRequests().at(-1)
  await click('Edit replanning details')
  await replaceInput('replan-minutes', '15')
  await replanEnergy('high')
  await replaceInput('replan-reason', 'I have more energy and fifteen minutes now.')
  await mode('replan-single')
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Finish the remaining test work' && !document.querySelector('[data-generation-loading]')"), 'edited replan new intent')
  assert.notEqual(replanRequests().at(-1).key, knownFailure.key)
  assert.equal(JSON.parse(replanRequests().at(-1).body).expected_revision, concurrentResume.body.revision)
  assert.equal((await json(`/api/questlines/${uiReplanId}`)).body.energy, 'high')
  assert.deepEqual((await json('/api/profile')).body, profileBeforeUIReplan)
  pass('Frontend stale replan and explicit input revision', 'Concurrent pause/resume makes the old form stale without changing its plan; canonical reload requires a fresh action; editing a definitively failed request uses the latest revision and a new key')

  const beforeAbandonedReplan = (await json(`/api/questlines/${uiReplanId}`)).body
  await click('Replan remaining stages')
  await replaceInput('replan-reason', 'Finish this request safely if I leave the page.')
  await mode('stages-2')
  replanGate = new Promise(resolve => { releaseReplan = resolve })
  await click('Generate revised stages')
  await until(() => evaluate("document.querySelector('[data-generation-loading]')?.matches(':modal')"), 'pending replan before navigation')
  // SPA navigation exercises React cleanup rather than resetting the document.
  await evaluate(`window.history.pushState({}, '', '/journey/${uiReplanId}'); window.dispatchEvent(new PopStateEvent('popstate'))`)
  await until(() => evaluate("document.querySelectorAll('[data-completed-stage]').length === 1 && document.body.style.overflow !== 'hidden' && !document.querySelector('[data-generation-loading]')"), 'abandoned replan cleans up modal')
  releaseReplan(); replanGate = null
  await until(async () => (await json(`/api/questlines/${uiReplanId}`)).body.plan_version === beforeAbandonedReplan.plan_version + 1, 'abandoned request may finish on server')
  assert.equal(await evaluate("location.pathname.startsWith('/journey/') && document.querySelectorAll('[data-completed-stage]').length === 1"), true)
  assert.deepEqual((await json('/api/profile')).body, profileBeforeUIReplan)
  await open(`/questlines/${uiReplanId}`)
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Sized stage 1'"), 'abandoned replan restored on return')
  await open(`/questlines/${lineId}`)
  await until(() => evaluate("document.body.innerText.includes('Campaign completed')"), 'completed campaign has no replan control')
  assert.equal(await evaluate("!!document.querySelector('.replan-panel')"), false)
  pass('Frontend replan navigation cleanup and completed guard', 'Leaving a pending request removes its modal and scroll lock; a later server result cannot overwrite another route, and returning reads the saved replacement; completed campaigns offer no replan control')

  if (process.argv.includes('--phase5a')) {
    await mode('qa-household')
    await startCheckIn('Clean my desk before studying using the storage and notes already beside it.', false, '15', 'low')
    await click('Generate My Quests')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Clear the desk'"), 'QA household save')
    const householdId = await evaluate("location.pathname.split('/').at(-1)")
    let household = (await json(`/api/questlines/${householdId}`)).body
    const householdBefore = (await json('/api/profile')).body
    assert.equal(household.progress.total_count, 2)
    assert.equal(household.current_quest.completion_encouragement, null)
    assert.equal(JSON.stringify(household).includes('Set up the study space'), false)
    assert.equal(await evaluate("document.body.innerText.includes('Set up the study space')"), false)
    assert.equal(await evaluate("document.querySelectorAll('.stage-locked').length"), 1)
    // Stop only our isolated FastAPI process, preserving its SQLite file.
    await new Promise(resolve => { backend.once('exit', resolve); backend.kill('SIGTERM') })
    await click('Complete stage')
    await until(() => evaluate("document.body.innerText.includes('Cannot reach FastAPI') && document.body.innerText.includes('Retry previous action')"), 'actual stopped backend error')
    assert.equal(await evaluate("!!document.querySelector('[data-completion-celebration]')"), false)
    backend = launchBackend()
    await until(async () => { try { return (await json('/api/health')).body.status === 'ok' } catch { return false } }, 'same QA DB backend restart')
    assert.deepEqual((await json(`/api/questlines/${householdId}`)).body, household)
    assert.deepEqual((await json('/api/profile')).body, householdBefore)
    await click('Retry previous action')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Set up the study space' && !!document.querySelector('[data-completion-message]')"), 'completion outage recovery')
    household = (await json(`/api/questlines/${householdId}`)).body
    assert.equal((await json('/api/profile')).body.total_xp, householdBefore.total_xp + 10)
    const repeated = await json(`/api/quests/${household.completed_quests[0].id}/complete`, { expected_revision: 1 })
    assert.equal(repeated.body.awarded_xp, 0)
    assert.equal(repeated.body.questline.completed_quests[0].completion_encouragement, household.completed_quests[0].completion_encouragement)
    await click('Continue Journey')
    await mode('unavailable')
    refreshAfterCompletion = true
    await click('Complete stage')
    await until(() => evaluate("document.body.innerText.includes('Campaign completed') && document.querySelectorAll('[data-history-encouragement]').length === 2"), 'refresh immediately after committed completion')
    household = (await json(`/api/questlines/${householdId}`)).body
    assert.equal(household.status, 'completed')
    assert.equal((await json('/api/profile')).body.total_xp, householdBefore.total_xp + 20)
    assert.equal(await evaluate("!!document.querySelector('[data-completion-celebration]')"), false)
    await screenshot('phase5a-household-completed')
    pass('Phase 5A A/E — household two-stage, real backend outage and immediate refresh', { id: householdId, campaignXP: 20, profileBefore: householdBefore, profileAfter: (await json('/api/profile')).body, history: household.completed_quests, model: 'mocked', actualBackendStoppedAndRestarted: true, completionDuringSimulatedOllamaOutage: true })

    await mode('qa-study')
    await startCheckIn('Study Python for and while loops using my existing notes and Python installation.', false, '60', 'medium')
    await click('Generate My Quests')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Read the loop notes'"), 'QA six-stage study save')
    const studyId = await evaluate("location.pathname.split('/').at(-1)")
    let study = (await json(`/api/questlines/${studyId}`)).body
    const studyBefore = (await json('/api/profile')).body
    let earned = 0
    const futureTitles = ['Run a for loop', 'Run a while loop', 'Compare the loop results', 'Check a boundary case', 'Test the loop knowledge']
    assert.equal(study.progress.total_count, 6)
    assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), 6)
    for (const title of futureTitles) {
      assert.equal(JSON.stringify(study).includes(title), false)
      assert.equal(await evaluate(`document.body.innerText.includes(${JSON.stringify(title)})`), false)
    }
    for (let index = 0; index < 6; index++) {
      const current = study.current_quest
      assert.equal(current.order, index + 1)
      assert.equal(current.completion_encouragement, null)
      const previousRevision = study.revision
      await click('Complete stage')
      await until(async () => { study = (await json(`/api/questlines/${studyId}`)).body; return study.revision > previousRevision }, 'QA stage commit ' + current.order)
      const completed = study.completed_quests.find(q => q.id === current.id)
      await until(() => evaluate(`document.querySelector('[data-completion-message]')?.textContent === ${JSON.stringify(completed.completion_encouragement)}`), 'QA encouragement ' + current.order)
      earned += current.xp_reward
      assert.equal(await evaluate(`document.querySelector('[data-completion-celebration]').textContent.includes(${JSON.stringify(`+${current.xp_reward} XP awarded`)})`), true)
      const profile = (await json('/api/profile')).body
      assert.equal(profile.total_xp, studyBefore.total_xp + earned)
      assert.equal(profile.level, Math.floor(profile.total_xp / 100) + 1)
      await until(() => evaluate(`document.querySelector('.profile-chips').textContent.includes(${JSON.stringify(`Level ${profile.level}`)}) && document.querySelector('.xp-total').textContent === ${JSON.stringify(`${profile.total_xp} XP`)}`), 'QA profile confirmed')
      assert.equal(study.progress.completed_count, index + 1)
      assert.equal(await evaluate("document.querySelectorAll('.stage-locked').length"), Math.max(0, 4 - index))
      await click('Continue Journey')
      if (index === 0) {
        const activeId = study.current_quest.id
        const history = study.completed_quests
        await click('Pause questline')
        await until(() => evaluate("document.body.innerText.includes('Resume questline')"), 'QA pause after progress')
        const paused = (await json(`/api/questlines/${studyId}`)).body
        await send('Page.reload', { ignoreCache: true })
        await until(() => evaluate("document.body.innerText.includes('Resume questline') && !!document.querySelector('.quest-title')"), 'QA paused browser restoration')
        assert.deepEqual((await json(`/api/questlines/${studyId}`)).body, paused)
        assert.equal(await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage').disabled"), true)
        await click('Resume questline')
        await until(() => evaluate("document.body.innerText.includes('Pause questline')"), 'QA resume same stage')
        study = (await json(`/api/questlines/${studyId}`)).body
        assert.equal(study.current_quest.id, activeId)
        assert.deepEqual(study.completed_quests, history)
        assert.equal((await json('/api/profile')).body.total_xp, studyBefore.total_xp + earned)
        pass('Phase 5A C — pause/reload/resume after completion', { activeId, preservedHistory: history, unchangedEarnedXP: earned, model: 'mocked' })
      }
      if (index === 2) {
        const snapshot = study
        await send('Page.reload', { ignoreCache: true })
        await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Compare the loop results'"), 'QA midway refresh')
        assert.deepEqual((await json(`/api/questlines/${studyId}`)).body, snapshot)
      }
    }
    assert.equal(study.status, 'completed')
    assert.equal(earned, 80)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.querySelectorAll('[data-history-encouragement]').length === 6"), 'QA six-stage final refresh')
    await screenshot('phase5a-six-completed')
    pass('Phase 5A B — six-stage study full walkthrough', { id: studyId, campaignXP: earned, profileBefore: studyBefore, profileAfter: (await json('/api/profile')).body, history: study.completed_quests, model: 'mocked', refreshedAfterThree: true })

    await mode('qa-study')
    await startCheckIn('Study Python for and while loops using my existing notes and Python installation.', false, '60', 'medium')
    await click('Generate My Quests')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Read the loop notes'"), 'QA replan source')
    const replanId = await evaluate("location.pathname.split('/').at(-1)")
    await click('Complete stage')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Run a for loop'"), 'QA replan one completed')
    const original = (await json(`/api/questlines/${replanId}`)).body
    const xpBeforeReplan = (await json('/api/profile')).body
    const body = { expected_revision: original.revision, available_minutes: 10, energy: 'low', reason: 'A smaller session remains; keep completed notes.' }
    await mode('stages-6') // Deliberately exceeds five remaining slots.
    const rejected = await json(`/api/questlines/${replanId}/replan`, body, randomUUID())
    assert.equal(rejected.status, 502)
    assert.equal(rejected.body.error.code, 'AI_INVALID_OUTPUT')
    assert.deepEqual((await json(`/api/questlines/${replanId}`)).body, original)
    assert.deepEqual((await json('/api/profile')).body, xpBeforeReplan)
    await mode('qa-replan')
    const key = randomUUID()
    const replacement = await json(`/api/questlines/${replanId}/replan`, body, key)
    assert.equal(replacement.status, 200)
    assert.equal(replacement.body.progress.total_count, 6)
    assert.equal(replacement.body.plan_version, 2)
    assert.deepEqual(replacement.body.completed_quests, original.completed_quests)
    assert.deepEqual((await json('/api/profile')).body, xpBeforeReplan)
    const replay = await json(`/api/questlines/${replanId}/replan`, body, key)
    assert.deepEqual(replay.body, replacement.body)
    const stale = await json(`/api/questlines/${replanId}/replan`, body, randomUUID())
    assert.equal(stale.status, 409)
    assert.equal(stale.body.error.code, 'STALE_REVISION')
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Replanned Run a for loop'"), 'QA replan UI canonical state')
    assert.equal(JSON.stringify(replacement.body).includes('"title":"Run a for loop"'), false)
    assert.equal(await evaluate("[...document.querySelectorAll('.campaign-stage-title,.quest-title')].some(h => h.textContent === 'Run a for loop')"), false)
    await screenshot('phase5a-api-replan')
    pass('Phase 5A D — API-initiated replan with frontend restoration', { id: replanId, completedHistory: replacement.body.completed_quests, XP: xpBeforeReplan, totalStages: 6, planVersion: 2, overCapError: rejected.body.error.code, staleError: stale.body.error.code, sameKeyReplayPreserved: true, frontendReplanControlImplemented: true, model: 'mocked' })

    await mode('qa-presentation')
    const missingTopicGoal = 'I need to present a complex topic that I know nothing about.'
    const checkInId = await startCheckIn(missingTopicGoal, false, '60', 'low')
    const unclear = (await json(`/api/check-in/${checkInId}`)).body
    assert.equal(unclear.status, 'needs_follow_up')
    await until(() => evaluate("!!document.querySelector('#clarification')"), 'QA presentation focused question')
    assert.equal(await evaluate("document.querySelector('.clarification-panel > p').textContent"), unclear.question)
    const answer = 'Introduce artificial intelligence to my classmates using my existing local notes, three slides and one timed five-minute rehearsal.'
    await input('clarification', answer)
    await click('Continue')
    await until(() => evaluate("!!document.querySelector('.ready-panel') && !document.querySelector('#clarification')"), 'QA presentation ready after one answer')
    const clarified = (await json(`/api/check-in/${checkInId}`)).body
    assert.equal(clarified.context.goal, missingTopicGoal)
    assert.equal(clarified.clarification_answer, answer)
    assert.equal(clarified.revision, 2)
    assert.equal(clarified.question, null)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("!!document.querySelector('.ready-panel')"), 'QA presentation answer refresh')
    await click('Generate My Quests')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Draft the AI introduction'"), 'QA clarified topic generation')
    const clarifiedId = await evaluate("location.pathname.split('/').at(-1)")
    const grounded = (await json(`/api/questlines/${clarifiedId}`)).body
    assert.ok(grounded.current_quest.action.includes('artificial intelligence'))
    assert.ok(grounded.current_quest.action.includes('exactly three slides'))
    assert.equal(grounded.progress.total_count, 2)
    pass('Phase 5A F — presentation topic clarification and grounded save', { question: unclear.question, originalGoal: clarified.context.goal, retainedAnswer: clarified.clarification_answer, revision: clarified.revision, currentQuest: grounded.current_quest, model: 'mocked', independentModelRelevanceProof: false })
  }

  if (process.argv.includes('--live-ai') || process.argv.includes('--live-campaign')) {
    await mode('real')
    if (!process.argv.includes('--live-campaign')) {
    const ambiguous = await startCheckIn('I need to present a complex topic that I know nothing about.', false, '240', 'low')
    const pendingTopic = (await json(`/api/check-in/${ambiguous}`)).body
    assert.equal(pendingTopic.status, 'needs_follow_up')
    await until(() => evaluate("!!document.querySelector('#clarification')"), 'live scenario B missing topic')
    assert.equal(await evaluate("document.querySelector('.clarification-panel > p').textContent"), pendingTopic.question)
    results.push({ name: 'Live scenario B clarification', result: 'PASS', evidence: { question: pendingTopic.question, inferenceAttempted: false } })
    console.log(JSON.stringify(results.at(-1)))
    }
    let liveSaved = false
    const liveScenarios = [
      { name: 'Requested AI presentation', goal: 'Prepare a 5-minute introduction to artificial intelligence for my classmates. Research the basics, create three slides, and practice.', minutes: '60', energy: 'medium' },
      { name: 'Constrained no-cook snack', goal: 'Make a no-cook vegetarian snack using only bread, tomato and cheese; no stove and no shopping', minutes: '10', energy: 'low' },
    ]
    for (const scenario of process.argv.includes('--live-campaign') ? liveScenarios.slice(1) : liveScenarios) {
      await startCheckIn(scenario.goal, false, scenario.minutes, scenario.energy)
      const generationStarted = Date.now()
      await click('Generate My Quests')
      await until(() => evaluate("location.pathname.startsWith('/questlines/') || !!document.querySelector('[role=alert]')"), 'live primary inference outcome', 155000)
      const result = await evaluate("({ saved: location.pathname.startsWith('/questlines/'), error: document.querySelector('[role=alert]')?.textContent ?? null })")
      if (!result.saved) {
        results.push({ name: 'Live primary inference: ' + scenario.name, result: 'RECOVERABLE_REJECTION', evidence: result })
        console.log(JSON.stringify(results.at(-1)))
        continue
      }
      const realId = await evaluate("location.pathname.split('/').at(-1)")
      const generationSeconds = (Date.now() - generationStarted) / 1000
      const before = (await json('/api/profile')).body
      const observed = []
      let real = (await json(`/api/questlines/${realId}`)).body
      assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), real.progress.total_count)
      assert.ok(real.progress.total_count >= 2 && real.progress.total_count <= 6)
      const objectiveCount = await evaluate("document.querySelectorAll('.stage-objectives input').length")
      assert.ok(objectiveCount >= 2 && objectiveCount <= 3)
      const checklistText = await evaluate("document.querySelector('.stage-objectives').innerText")
      assert.ok(checklistText.includes(real.current_quest.completion_criteria))
      assert.equal(await evaluate("document.querySelectorAll('.stage-locked .stage-objectives').length"), 0)
      await screenshot('live-campaign-first-stage')
      await mode('unavailable') // Completion must work with no local inference.
      for (let count = 0; real.status !== 'completed'  && count < 6; count++) {
        assert.equal(real.status, 'active'); assert.ok(real.current_quest)
        observed.push(real.current_quest)
        await until(() => evaluate(`document.querySelector('.quest-title')?.textContent === ${JSON.stringify(real.current_quest.title)}`), 'actual generated current quest')
        await click('Complete stage')
        const prior = real.revision
        await until(async () => { real = (await json(`/api/questlines/${realId}`)).body; return real.revision > prior }, 'real explicit completion')
        await until(() => evaluate(real.status === 'completed' ? "document.body.innerText.includes('Questline completed')" : `document.querySelector('.quest-title')?.textContent === ${JSON.stringify(real.current_quest.title)}`), 'confirmed real progression')
        const completed = real.completed_quests.find(q => q.id === observed.at(-1).id)
        observed[observed.length - 1] = completed
        await until(() => evaluate(`document.querySelector('[data-completion-message]')?.textContent === ${JSON.stringify(completed.completion_encouragement)}`), 'real contextual completion encouragement')
        assert.equal(await evaluate(`document.querySelector('[data-completion-celebration]').textContent.includes(${JSON.stringify(`+${completed.xp_reward} XP awarded`)})`), true)
        if (real.current_quest) assert.equal(real.current_quest.completion_encouragement, null)
        await screenshot(`live-celebration-${count + 1}`)
        await click('Continue Journey')
      }
      assert.equal(real.status, 'completed')
      assert.equal(real.progress.completed_count, real.progress.total_count)
      await send('Page.reload', { ignoreCache: true })
      await until(() => evaluate("document.body.innerText.includes('Questline completed')"), 'completed real questline refresh')
      const after = (await json('/api/profile')).body
      assert.ok(after.total_xp > before.total_xp)
      assert.equal(await evaluate("document.querySelector('[data-campaign-xp]').textContent"), `${after.total_xp - before.total_xp} XP`)
      assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), real.progress.total_count)
      assert.equal(await evaluate("document.querySelectorAll('[data-history-encouragement]').length"), real.progress.total_count)
      await screenshot('live-generated-completed')
      results.push({ name: 'Live primary inference and full frontend completion: ' + scenario.name, result: 'PASS', evidence: { model: 'qwen3:1.7b', generationSeconds, questlineId: realId, profileBefore: before, profileAfter: after, completedQuests: observed, statusAfterRefresh: real.status, ollamaUnavailableDuringCompletion: true, syntheticExplicitCompletion: true, actualUserTaskExecution: false } })
      console.log(JSON.stringify(results.at(-1)))
      liveSaved = true
      break
    }
    if (!liveSaved) results.push({ name: 'Real frontend completion', result: 'UNVERIFIED', evidence: 'Both bounded real generation attempts were rejected; no fabricated or seeded fallback.' })
  }
  await writeFile(join(temp, 'results.json'), JSON.stringify(results, null, 2))
  console.log(JSON.stringify({ evidenceDirectory: temp, browserCases: results.filter(r => !r.name.startsWith('Live ')).length, liveCases: results.filter(r => r.name.startsWith('Live ')).length, mockedOllama: true, liveAiAttempted: process.argv.includes('--live-ai') || process.argv.includes('--live-campaign') }))
} catch (error) {
  results.push({ name: 'Harness failure', result: 'FAIL', evidence: String(error) })
  await writeFile(join(temp, 'results.json'), JSON.stringify(results, null, 2))
  console.error(JSON.stringify({ evidenceDirectory: temp, failure: String(error) }))
  throw error
} finally {
  socket?.close()
  for (const child of children.reverse()) {
    child.kill('SIGTERM')
    await Promise.race([new Promise(resolve => child.once('exit', resolve)), pause(500)])
  }
}
