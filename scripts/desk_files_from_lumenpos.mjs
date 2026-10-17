// Lumen Restaurants' own Frappe 16 desk files, made from LumenPOS's (0.61.3).
//
// LumenPOS ships four JSON files that Frappe 16 imports on every migrate: a
// desktop icon and a workspace sidebar (the icon grid), a module sidebar and a
// dock (16.5x, the module-first desk). A merge brings them naming LumenPOS,
// under lumenpos/ or, when git follows the folder rename, under our folder with
// LumenPOS's file names. This script writes ours, with our app, module, title
// and logo and our restaurant doctypes in their own section, and removes
// LumenPOS's copies wherever they landed. Run it after every merge:
//
//   node scripts/desk_files_from_lumenpos.mjs          write ours, drop theirs
//   node scripts/desk_files_from_lumenpos.mjs --check  say what is out of step
//
// One file of ours has no LumenPOS original: a HIDDEN tile named after our
// workspace ("LumenPOS", the name it keeps on purpose). In grid mode Frappe 16
// makes a tile by itself for every public workspace that has none with its
// label, so without it a site shows two tiles of ours, the second leading to a
// sidebar that does not exist (what LumenPOS's Zimbabwe shop saw). Hiding the
// workspace tile of an app that has its own is what Frappe does itself
// (desktop_icon.create_desktop_icons_from_workspace).
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const CHECK = process.argv.includes('--check')
const APP = 'lumen_restaurants'
const TITLE = 'Lumen Restaurants'
const MODULE = 'Lumen Restaurants'
const WORKSPACE = 'LumenPOS'
const LOGO = `/assets/${APP}/pos/pwa-192.png`

// LumenPOS's file, where a merge may leave it, and ours.
const FILES = [
  [['lumenpos/desktop_icon/lumenpos.json', `${APP}/desktop_icon/lumenpos.json`], `${APP}/desktop_icon/${APP}.json`],
  [['lumenpos/workspace_sidebar/lumenpos.json', `${APP}/workspace_sidebar/lumenpos.json`], `${APP}/workspace_sidebar/${APP}.json`],
  [['lumenpos/lumenpos/sidebar/lumenpos/lumenpos.json', `${APP}/${APP}/sidebar/lumenpos/lumenpos.json`,
    `${APP}/lumenpos/sidebar/lumenpos/lumenpos.json`], `${APP}/${APP}/sidebar/${APP}/${APP}.json`],
  [['lumenpos/dock/lumenpos/lumenpos.json', `${APP}/dock/lumenpos/lumenpos.json`], `${APP}/dock/${APP}/${APP}.json`],
]
const HIDDEN = `${APP}/desktop_icon/lumenpos_workspace.json`

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

function source(froms) {
  for (const from of froms) {
    const local = path.join(ROOT, from)
    if (fs.existsSync(local)) return fs.readFileSync(local, 'utf8')
  }
  return execFileSync('git', ['-C', ROOT, 'show', `lumenpos/main:${froms[0]}`], { encoding: 'utf8' })
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
    j.logo_url = LOGO
    return j
  }
  // The two sidebars. Home stays the workspace "LumenPOS": its record keeps
  // LumenPOS's name on purpose (see CLAUDE.md), so link_to is already right.
  j.name = TITLE
  j.title = TITLE
  const at = j.items.findIndex((i) => i.link_to === 'POS Profile' && !i.child)
  if (at < 0) throw new Error('no POS Profile row in ' + j.doctype)
  const head = { ...(j.items.find((i) => i.type === 'Section Break') || {}), label: 'Restaurant', icon: ICON }
  const rows = RESTAURANT.map((dt) => ({
    ...j.items.find((i) => i.child && i.type === 'Link'),
    label: dt,
    link_to: dt,
    link_type: 'DocType',
  }))
  if (!j.items.some((i) => i.label === 'Restaurant')) j.items.splice(at + 1, 0, head, ...rows)
  return j
}

function hidden(icon) {
  // From our own tile, so the fields follow LumenPOS's shape. Its modified is
  // later than any tile Frappe made by itself, so the import replaces that one.
  const j = structuredClone(icon)
  j.name = WORKSPACE
  j.label = WORKSPACE
  j.hidden = 1
  j.idx = (j.idx || 0) + 1
  delete j.logo_url
  return j
}

const wanted = []
for (const [froms, to] of FILES) {
  const doc = ours(JSON.parse(source(froms)))
  wanted.push([to, doc])
  if (doc.doctype === 'Desktop Icon') wanted.push([HIDDEN, hidden(doc)])
}

let out = 0
for (const [to, doc] of wanted) {
  const want = JSON.stringify(doc, null, 1) + '\n'
  const dest = path.join(ROOT, to)
  const have = fs.existsSync(dest) ? fs.readFileSync(dest, 'utf8') : null
  if (CHECK) {
    if (have !== want) { console.log('out of step: ' + to); out++ }
    continue
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  if (have !== want) fs.writeFileSync(dest, want)
  console.log((have === want ? 'same ' : 'wrote ') + to)
}
for (const [froms] of FILES) {
  for (const from of froms) {
    const p = path.join(ROOT, from)
    if (!fs.existsSync(p)) continue
    if (CHECK) { console.log('LumenPOS copy still here: ' + from); out++; continue }
    try {
      execFileSync('git', ['-C', ROOT, 'rm', '-q', '-f', '--', from], { stdio: 'pipe' })
    } catch {
      fs.rmSync(p)
    }
    console.log('removed ' + from)
  }
}
if (CHECK) {
  console.log(out ? out + ' to fix' : 'desk files in step')
  process.exit(out ? 1 : 0)
}
