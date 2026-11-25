import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir } from 'node:fs/promises'

// Point at an isolated Frappe site with the fiscal-audit fixtures.
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = process.env.FISCAL_TEST_ORIGIN
const password = process.env.AUDIT_FIXTURE_PASSWORD
const assets = process.env.TAX_ASSETS
assert(origin && password && assets)
const { hostname, port } = new URL(origin)
await mkdir(assets, { recursive: true })
const browser = await chromium.launch({ args: [
  '--no-sandbox', '--no-proxy-server',
  `--host-resolver-rules=MAP ${hostname} 127.0.0.1`,
] })
const clean = text => text.replace(/[\u2068\u2069]/g, '').replace(/\s/g, ' ')
const cash = 'Espèces XAF audit'

try {
  for (const hasAny of [true, false]) {
    const context = await browser.newContext({ locale: 'fr-FR', viewport: { width: 1440, height: 1024 } })
    const response = await context.request.post(`http://127.0.0.1:${port}/api/method/login`, {
      headers: { Host: hostname }, form: { usr: 'Administrator', pwd: password },
    })
    assert.equal(response.status(), 200)
    const sid = (await context.cookies()).find(cookie => cookie.name === 'sid')
    await context.addCookies([{ name: 'sid', value: sid.value, domain: hostname, path: '/' }])
    const page = await context.newPage()
    await page.addInitScript(enabled => {
      if (!enabled) Object.defineProperty(AbortSignal, 'any', { value: undefined })
      localStorage.setItem('lumenpos_profile', 'Correction fiscale HT')
    }, hasAny)
    await page.clock.install()
    await page.goto(origin + '/pos')
    await page.getByText('Plus tard', { exact: true }).click({ timeout: 3500 }).catch(() => {})
    const quotes = '**/*.quote_sale'
    let scenario = 'native'
    let renewal
    let unblock
    let blocked = false
    let requests = 0
    await page.route(quotes, async route => {
      requests++
      if (scenario === 'held') {
        blocked = true
        await new Promise(resolve => { unblock = resolve })
      }
      if (scenario === 'failed') return route.fulfill({ status: 503, json: {} })
      const endpoint = new URL(route.request().url())
      endpoint.hostname = '127.0.0.1'
      const native = await route.fetch({
        url: endpoint.href,
        headers: { ...await route.request().allHeaders(), Host: hostname },
      })
      if (!['vat', 'centimes', 'allocation'].includes(scenario)) return route.fulfill({ response: native })
      const body = await native.json()
      const q = body.message
      if (scenario === 'vat') {
        q.payable = 121000
        q.taxes[0].amount = 20000
        q.taxes[1].amount = 1000
      } else if (scenario === 'centimes') {
        q.payable = 119800
        q.taxes[1].amount = 1800
      } else {
        q.taxes[0].amount = 17500
        q.taxes[1].amount = 1400
      }
      q.fiscal_fingerprint = scenario
      await route.fulfill({ response: native, json: body })
    })
    await page.locator('.rmenu,.catalog').getByText('TAXAUDIT-100K', { exact: true }).first().click()
    const pay = page.locator('[data-tour=cart-pay]').first()
    const totals = page.locator('.rtotals')
    const retryCart = totals.getByRole('button', { name: /Réessayer|Retry/ })
    const renew = async mode => {
      scenario = mode
      const next = page.waitForResponse(response => response.url().endsWith('.quote_sale'))
      await page.clock.fastForward(30_100)
      await next
    }
    await pay.getByText(/118.900/).waitFor()
    const initialRequests = requests
    for (let i = 0; i < 4; i++) {
      await renew('native')
      await pay.getByText(/118.900/).waitFor()
    }
    assert.equal(requests - initialRequests, 4)
    await renew('vat')
    await pay.getByText(/121.000/).waitFor()
    if (hasAny) await totals.screenshot({ path: assets + '/panier-renouvele.png' })
    await renew('failed')
    await totals.getByText(/Impossible de vérifier/).waitFor()
    assert.equal(await totals.getByText(/Calcul des taxes/).count(), 0)
    if (hasAny) await totals.screenshot({ path: assets + '/panier-renouvellement-echec.png' })
    const failedCount = requests
    await page.clock.fastForward(60_000)
    assert.equal(requests, failedCount)
    scenario = 'native'
    await retryCart.click()
    await pay.getByText(/118.900/).waitFor()
    await page.evaluate(() => { location.hash = '/history' })
    await pay.waitFor({ state: 'detached' })
    const closedCount = requests
    await page.clock.fastForward(31_000)
    assert.equal(requests, closedCount)
    scenario = 'held'
    await page.evaluate(() => { location.hash = '/' })
    await pay.click()
    const overlay = page.locator('.pay-overlay')
    const complete = overlay.locator('.complete')
    const due = overlay.locator('.due-value')
    const chooseCash = () => overlay.getByText(cash, { exact: true }).first().click()
    const confirm = overlay.getByRole('button', { name: /confirmer le nouveau total/i })
    for (let i = 0; i < 30 && !blocked; i++) await new Promise(resolve => setTimeout(resolve, 100))
    assert.equal(blocked, true)
    assert.equal(await complete.isVisible(), false)
    scenario = 'native'
    unblock()
    blocked = false
    await due.waitFor()
    assert.equal(await page.evaluate(() => typeof AbortSignal.any), hasAny ? 'function' : 'undefined')
    assert.match(clean(await due.innerText()), /118 900/)
    await chooseCash()
    assert.equal(await complete.isEnabled(), true)
    if (hasAny) {
      scenario = 'held'
      await page.clock.fastForward(30_100)
      await due.waitFor({ state: 'hidden' })
      await overlay.screenshot({ path: assets + '/devis-expire.png' })
      for (let i = 0; i < 30 && !blocked; i++) await new Promise(resolve => setTimeout(resolve, 100))
      assert.equal(blocked, true)
      renewal = page.waitForResponse(response => response.url().endsWith('.quote_sale'))
      scenario = 'native'
      unblock()
      await renewal
      await due.waitFor()
      assert.equal(await complete.isEnabled(), true)
      await renew('allocation')
      await overlay.getByText(/ventilation fiscale a changé/).waitFor()
      assert.equal(await complete.isEnabled(), true)
      await overlay.screenshot({ path: assets + '/ventilation-modifiee.png' })
      await renew('vat')
      await confirm.waitFor()
      assert.equal(await complete.isVisible(), false)
      await overlay.screenshot({ path: assets + '/nouveau-total-a-confirmer.png' })
      await confirm.click()
      assert.equal(await complete.isEnabled(), false)
      assert.match(clean(await due.innerText()), /121 000/)
      await chooseCash()
      await renew('centimes')
      await confirm.waitFor()
      await confirm.click()
      assert.match(clean(await due.innerText()), /119 800/)
      await renew('failed')
      const retry = overlay.getByRole('button', { name: /Réessayer|Retry/ })
      await retry.waitFor()
      assert.equal(await complete.isVisible(), false)
      scenario = 'native'
      await retry.click()
      await confirm.waitFor()
      await confirm.click()
      await due.waitFor()
      assert.match(clean(await due.innerText()), /118 900/)
      await chooseCash()
    }
    const posting = page.waitForResponse(response => response.url().endsWith('.submit_sale'))
    await complete.click()
    const result = await posting
    assert.equal(result.status(), 200)
    const { message: receipt } = await result.json()
    assert.equal(receipt.rounded_total || receipt.grand_total, 118900)
    console.log(JSON.stringify({ hasAbortSignalAny: hasAny, facture: receipt.name, montant: 118900 }))
    await context.close()
  }
} finally {
  await browser.close()
}
