// Lumen Restaurants' own Frappe 16 desk files, made from LumenPOS's (0.61.3).
//
// LumenPOS ships four JSON files that Frappe 16 imports on every migrate: a
// desktop icon and a workspace sidebar (16.0 to 16.4x, the icon grid), a module
// sidebar and a dock (16.5x, the module-first desk). A merge brings them under
// lumenpos/ naming LumenPOS. This script writes ours under lumen_restaurants/,
// with our app, module and title, our restaurant doctypes in their own section,
// and removes LumenPOS's copies. Run it after every merge that touches them:
//
//   node scripts/desk_files_from_lumenpos.mjs          write ours, drop theirs
//   node scripts/desk_files_from_lumenpos.mjs --check  say what is out of step
//
// The source is LumenPOS's file in the working tree when a merge just brought
// it, else the one in the `lumenpos/main` ref.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const CHECK = process.argv.includes('--check')
const APP = 'lumen_restaurants'
const TITLE = 'Lumen Restaurants'
const MODULE = 'Lumen Restaurants'

const FILES = [
  ['lumenpos/desktop_icon/lumenpos.json', `${APP}/desktop_icon/${APP}.json`],
  ['lumenpos/workspace_sidebar/lumenpos.json', `${APP}/workspace_sidebar/${APP}.json`],
  ['lumenpos/lumenpos/sidebar/lumenpos/lumenpos.json', `${APP}/${APP}/sidebar/${APP}/${APP}.json`],
  ['lumenpos/dock/lumenpos/lumenpos.json', `${APP}/dock/${APP}/${APP}.json`],
]

// Our restaurant doctypes, in the order a manager looks for them. Placed after
// the outlets (POS Profile), before LumenPOS's own sections.
const RESTAURANT = [
  'POS Restaurant Table',
  'POS Floor Area',
  'POS Restaurant Order',
  'POS Kitchen Ticket',
  'POS Table Reservation',
  'POS Booking Page',
  'POS Modifier Group',
]
// The section's icon, from the lucide set both desks draw from.
const ICON = 'utensils'

function source(from) {
  const local = path.join(ROOT, from)
  if (fs.existsSync(local)) return fs.readFileSync(local, 'utf8')
  return execFileSync('git', ['-C', ROOT, 'show', `lumenpos/main:${from}`], { encoding: 'utf8' })
}

function ours(doc) {
  const j = structuredClone(doc)
  j.app = APP
  if (j.module) j.module = MODULE
  if (j.doctype === 'Dock') {
    j.name = APP
    for (const it of j.items) {
      if (it.link_type === 'Sidebar' && it.link_to === 'LumenPOS') it.link_to = TITLE
      if (it.title === 'LumenPOS') it.title = TITLE
    }
    if (j.mount_on) throw new Error('LumenPOS dock mounts on ' + j.mount_on + ': ours must not (it loses our apps tile)')
    return j
  }
  if (j.doctype === 'Desktop Icon') {
    j.name = TITLE
    j.label = TITLE
    if (j.link_to === 'LumenPOS') j.link_to = TITLE
    return j
  }
  // The two sidebars. Home stays the workspace "LumenPOS": its record keeps
  // LumenPOS's name on purpose (see CLAUDE.md), so link_to is already right.
  j.name = TITLE
  j.title = TITLE
  const at = j.items.findIndex((i) => i.link_to === 'POS Profile' && !i.child)
  if (at < 0) throw new Error('no POS Profile row in ' + j.doctype)
  const head = {
    ...Object.fromEntries(Object.entries(j.items.find((i) => i.type === 'Section Break') || {})),
    label: 'Restaurant',
    icon: ICON,
  }
  const rows = RESTAURANT.map((dt) => {
    const r = { ...j.items.find((i) => i.child && i.type === 'Link') }
    r.label = dt
    r.link_to = dt
    r.link_type = 'DocType'
    return r
  })
  if (!j.items.some((i) => i.label === 'Restaurant')) j.items.splice(at + 1, 0, head, ...rows)
  return j
}

let out = 0
for (const [from, to] of FILES) {
  const want = JSON.stringify(ours(JSON.parse(source(from))), null, 1) + '\n'
  const dest = path.join(ROOT, to)
  const have = fs.existsSync(dest) ? fs.readFileSync(dest, 'utf8') : null
  if (CHECK) {
    if (have !== want) { console.log('out of step: ' + to); out++ }
    if (fs.existsSync(path.join(ROOT, from))) { console.log('LumenPOS copy still here: ' + from); out++ }
    continue
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  if (have !== want) fs.writeFileSync(dest, want)
  console.log((have === want ? 'same ' : 'wrote ') + to)
}
if (CHECK) {
  console.log(out ? out + ' to fix' : 'desk files in step')
  process.exit(out ? 1 : 0)
}
for (const [from] of FILES) {
  const p = path.join(ROOT, from)
  if (fs.existsSync(p)) {
    execFileSync('git', ['-C', ROOT, 'rm', '-q', '-f', '--', from])
    console.log('removed ' + from)
  }
}
