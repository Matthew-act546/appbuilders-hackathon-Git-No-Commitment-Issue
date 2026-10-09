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
  start(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'preview', '--', '--port', '4184'], join(root, 'frontend'))
  await until(async () => { try { return (await fetch(origin)).ok } catch { return false } }, 'production preview')
  start(process.env.CHROMIUM_BINARY || 'chromium', ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9229', `--user-data-dir=${join(temp, 'browser')}`, 'about:blank'], root)
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
      if (refreshAfterCompletion && request.method === 'POST' && url.pathname.endsWith('/complete') && response.ok) {
        refreshAfterCompletion = false
        // The real DB has committed; reload before React receives confirmation.
        await send('Page.reload', { ignoreCache: true })
        try { await send('Fetch.failRequest', { requestId, errorReason: 'Aborted' }) } catch {}
        return
      }
      if (corruptDetail && request.method === 'GET' && /^\/api\/questlines\//.test(url.pathname) && response.ok) body = JSON.stringify({ ...JSON.parse(body), locked_quests: [{ title: 'SECRET_FUTURE' }] })
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
  async function evaluate(expression) { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value }
  async function open(path) { await send('Page.navigate', { url: origin + path }); await until(() => evaluate(`location.pathname === ${JSON.stringify(path.split('?')[0])} && !!document.querySelector('main h1') && document.readyState === 'complete'`), 'page ' + path) }
  async function click(text) { await until(() => evaluate(`[...document.querySelectorAll('main button')].some(b => b.textContent === ${JSON.stringify(text)} && !b.disabled)`), 'enabled button ' + text); await evaluate(`[...document.querySelectorAll('main button')].find(b => b.textContent === ${JSON.stringify(text)}).click()`) }
  async function input(id, value) {
    await evaluate(`document.getElementById(${JSON.stringify(id)}).focus()`)
    await send('Input.insertText', { text: value })
    await until(() => evaluate(`document.getElementById(${JSON.stringify(id)}).value === ${JSON.stringify(value)}`), 'input ' + id)
  }
  async function energy(value = 'low') { await evaluate(`const e = document.getElementById('energy'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e, ${JSON.stringify(value)}); e.dispatchEvent(new Event('change',{bubbles:true}))`) }
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
  async function screenshot(name) { const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true }); await writeFile(join(temp, name + '.png'), Buffer.from(r.data, 'base64')) }
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable')
  await send('Fetch.enable', { patterns: [{ urlPattern: '*://*/api/*', requestStage: 'Request' }] })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })

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
  await click('Generate My Quests')
  await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent.includes('Generating quests locally')).click()")
  await until(() => evaluate("location.pathname.startsWith('/questlines/') && document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint'"), 'saved questline navigation')
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

  await send('Page.reload', { ignoreCache: true })
  await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Inspect the endpoint'"), 'refresh restoration')
  assert.equal(await evaluate("[...document.querySelectorAll('.stage-objectives input')].some(i => i.checked)"), false)
  await click('Pause questline')
  await until(() => evaluate("[...document.querySelectorAll('main button')].some(b => b.textContent === 'Resume questline')"), 'pause committed')
  assert.equal(await evaluate("[...document.querySelectorAll('main button')].find(b => b.textContent === 'Complete stage').disabled"), true)
  assert.equal((await json(`/api/questlines/${lineId}`)).body.current_quest.id, firstId)
  await click('Resume questline')
  await until(() => evaluate("[...document.querySelectorAll('main button')].some(b => b.textContent === 'Pause questline')"), 'resume committed')
  assert.equal((await json('/api/profile')).body.total_xp, 0)
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
  await click('Continue Journey')
  assert.equal(await evaluate("document.activeElement?.id"), `campaign-map-${lineId}`)
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
    await click('Complete stage')
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Sized stage 2'"), `unlock second of ${count}`)
    const duplicate = await json(`/api/quests/${first.id}/complete`, { expected_revision: 1 })
    assert.equal(duplicate.body.awarded_xp, 0)
    assert.equal((await json('/api/profile')).body.total_xp, before + 10)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.querySelector('.quest-title')?.textContent === 'Sized stage 2'"), `refresh ${count} stages`)
    assert.equal(await evaluate("document.querySelectorAll('.campaign-node').length"), count)
    for (let index = 1; index < count; index++) {
      await click('Complete stage')
      await until(() => evaluate(index + 1 === count ? "document.body.innerText.includes('Campaign completed')" : `document.querySelector('.quest-title')?.textContent === 'Sized stage ${index + 2}'`), `complete sized stage ${index + 1}`)
    }
    sized = (await json(`/api/questlines/${id}`)).body
    assert.equal(sized.status, 'completed')
    assert.equal((await json('/api/profile')).body.total_xp, before + count * 10)
    await send('Page.reload', { ignoreCache: true })
    await until(() => evaluate("document.body.innerText.includes('Campaign completed')"), `completed sized ${count} refresh`)
    assert.equal(await evaluate("document.querySelector('[data-campaign-xp]').textContent"), `${count * 10} XP`)
    pass(`${count}-stage Campaign Map integration`, 'Mocked count selection, real API/SQLite: current-only content, anonymous locked stages, three temporary checkpoints, one-time XP, sequential unlocking and completed refresh persistence')
  }

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
    pass('Phase 5A D — API-initiated replan with frontend restoration', { id: replanId, completedHistory: replacement.body.completed_quests, XP: xpBeforeReplan, totalStages: 6, planVersion: 2, overCapError: rejected.body.error.code, staleError: stale.body.error.code, sameKeyReplayPreserved: true, frontendReplanControlImplemented: false, model: 'mocked' })

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
