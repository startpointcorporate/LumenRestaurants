// Copyright (c) 2026 Lumen Solutions
// SPDX-License-Identifier: AGPL-3.0-only
// "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
//
// The installed-app icons, drawn as pixels and encoded as PNG here so the repo
// needs no image toolchain (the same approach as LumenPOS's own). The mark is
// a table with four chairs seen from above, white on the LumenPOS brand
// square: the same shape as the favicon in www/restaurant.html.
import { deflateSync } from 'node:zlib'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Written into the Vite public folder, from where every build copies them
// into the shipped asset folder.
const OUT = fileURLToPath(new URL('../frontend/public/', import.meta.url))

// brand gradient ends, top-left to bottom-right
const C1 = [42, 123, 255]
const C2 = [11, 67, 184]

// In the 100x100 space of the favicon: the table, then the chairs.
const DISCS = [
  [50, 50, 15],
  [50, 24, 6],
  [50, 76, 6],
  [24, 50, 6],
  [76, 50, 6],
]
const SUB = 4 // 4x4 samples per pixel for smooth edges

function inRounded(x, y, size) {
  const radius = size * 0.22
  const near = (cx, cy) => (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
  if (x >= radius && x <= size - radius) return true
  if (y >= radius && y <= size - radius) return true
  return near(radius, radius) || near(size - radius, radius) || near(radius, size - radius) || near(size - radius, size - radius)
}

function inGlyph(x, y, size) {
  const s = size / 100
  return DISCS.some(([cx, cy, r]) => (x - cx * s) ** 2 + (y - cy * s) ** 2 <= (r * s) ** 2)
}

function draw(size) {
  const px = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      let inside = 0
      let white = 0
      for (let sy = 0; sy < SUB; sy += 1) {
        for (let sx = 0; sx < SUB; sx += 1) {
          const fx = x + (sx + 0.5) / SUB
          const fy = y + (sy + 0.5) / SUB
          if (!inRounded(fx, fy, size)) continue
          inside += 1
          if (inGlyph(fx, fy, size)) white += 1
        }
      }
      const i = (y * size + x) * 4
      if (!inside) {
        px[i + 3] = 0
        continue
      }
      const t = (x / size + y / size) / 2
      const base = C1.map((c, k) => c + (C2[k] - c) * t)
      const w = white / inside
      px[i] = Math.round(base[0] + (255 - base[0]) * w)
      px[i + 1] = Math.round(base[1] + (255 - base[1]) * w)
      px[i + 2] = Math.round(base[2] + (255 - base[2]) * w)
      px[i + 3] = Math.round((255 * inside) / (SUB * SUB))
    }
  }
  return px
}

let table = null
function crc32(buf) {
  if (!table) {
    table = new Int32Array(256)
    for (let n = 0; n < 256; n += 1) {
      let c = n
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
      table[n] = c
    }
  }
  let c = -1
  for (const byte of buf) c = table[(c ^ byte) & 0xff] ^ (c >>> 8)
  return c ^ -1
}

function png(size) {
  const px = draw(size)
  const raw = Buffer.alloc((size * 4 + 1) * size)
  for (let y = 0; y < size; y += 1) {
    raw[y * (size * 4 + 1)] = 0 // filter: none
    px.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4)
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4)
    len.writeUInt32BE(data.length)
    const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
    const crc = Buffer.alloc(4)
    crc.writeUInt32BE(crc32(body) >>> 0)
    return Buffer.concat([len, body, crc])
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

for (const size of [192, 512]) {
  const file = OUT + `icon-${size}.png`
  writeFileSync(file, png(size))
  console.log('wrote', file)
}
