import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'vite'

const vite = await createServer({ configFile: false, server: { middlewareMode: true, ws: false } })
globalThis.window = { addEventListener() {}, csrf_token: '' }
globalThis.document = { documentElement: {}, createElement: () => ({}) }
const { call, OfflineError } = await vite.ssrLoadModule('/src/api.js')
test.after(() => vite.close())

test('API deadline and cancellation work with and without AbortSignal.any', async () => {
  const originalAny = Object.getOwnPropertyDescriptor(AbortSignal, 'any')
  const originalFetch = globalThis.fetch
  const originalWindow = globalThis.window
  globalThis.window = { csrf_token: '' }
  try {
    for (const hasAny of [true, false]) {
      Object.defineProperty(AbortSignal, 'any', {
        configurable: true, value: hasAny ? () => { throw new Error('unexpected dependency') } : undefined,
      })
      const upstream = new AbortController()
      const active = new Set()
      const add = upstream.signal.addEventListener.bind(upstream.signal)
      const remove = upstream.signal.removeEventListener.bind(upstream.signal)
      upstream.signal.addEventListener = (type, cb, options) => {
        active.add(cb)
        add(type, cb, options)
      }
      upstream.signal.removeEventListener = (type, cb) => {
        active.delete(cb)
        remove(type, cb)
      }
      globalThis.fetch = async (_path, { signal }) => {
        assert.equal(signal.aborted, false)
        return { ok: true, json: async () => ({ message: 118900 }) }
      }
      assert.equal(await call('quote', {}, { signal: upstream.signal }), 118900)
      assert.equal(active.size, 0)
      globalThis.fetch = (_path, { signal }) => new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
      })
      const pending = call('quote', {}, { signal: upstream.signal })
      upstream.abort()
      await assert.rejects(pending, OfflineError)
      assert.equal(active.size, 0)

      const timeout = new AbortController()
      await assert.rejects(call('quote', {}, { signal: timeout.signal, timeout: 10 }), OfflineError)
      assert.equal(timeout.signal.aborted, false)

      globalThis.fetch = async (_path, { signal }) => {
        assert.equal(signal.aborted, true)
        throw new Error('already aborted')
      }
      await assert.rejects(call('quote', {}, { signal: upstream.signal }), OfflineError)
    }
  } finally {
    if (originalAny) Object.defineProperty(AbortSignal, 'any', originalAny)
    else delete AbortSignal.any
    globalThis.window = originalWindow
    globalThis.fetch = originalFetch
  }
})
