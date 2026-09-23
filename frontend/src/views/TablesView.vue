<!-- Copyright (c) 2026 Lumen Solutions
     SPDX-License-Identifier: AGPL-3.0-only
     "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md. -->
<template>
  <div class="floor">
    <div class="card floor-card">
      <div class="floor-head">
        <div class="area-tabs">
          <button
            class="area-tab"
            :class="{ active: area === null }"
            @click="area = null"
          >
            {{ t('All') }}
            <span class="count">{{ tables.length }}</span>
          </button>
          <button
            v-for="name in areas"
            :key="name"
            class="area-tab"
            :class="{ active: area === name }"
            @click="area = name"
          >
            {{ name || t('Floor') }}
          </button>
        </div>
        <div class="head-actions">
          <button class="btn btn-outline" :disabled="!canOpen" @click="startLoose('Takeaway')">
            <Icon name="bag" /> {{ t('Takeaway') }}
          </button>
          <button class="btn btn-outline" @click="load">
            <Icon name="refresh" />
          </button>
        </div>
      </div>

      <div v-if="session.offline" class="empty muted">
        {{ t('Tables need a connection: the order is shared between every device in the place.') }}
      </div>
      <div v-else-if="loading" class="empty muted">{{ t('Loading…') }}</div>
      <div v-else-if="!tables.length && !loose.length" class="empty muted">
        {{ t('No tables yet. Add them under Settings, General, Restaurant.') }}
      </div>

      <div v-else class="floor-body">
        <div class="table-grid">
          <div
            v-for="table in shown"
            :key="table.name"
            class="table-card"
            :class="{ busy: table.order }"
          >
            <button class="table-main" @click="openTable(table)">
              <div class="t-head">
                <span class="t-no">{{ table.table_no }}</span>
                <span class="t-seats">{{ table.seats || 0 }}</span>
              </div>
              <div v-if="table.order" class="t-open">
                <div class="t-total">{{ money(table.order.total) }}</div>
                <div class="t-meta">
                  {{ sinceText(table.order.opened_at) }}
                  <span v-if="table.order.guests">&nbsp;· {{ table.order.guests }}</span>
                </div>
                <div class="t-meta who">{{ table.order.opened_by_name }}</div>
              </div>
              <div v-else class="t-free">{{ t('Free') }}</div>
            </button>
            <button
              v-if="table.order"
              class="t-more"
              :title="t('More')"
              @click.stop="menuFor = menuFor === table.order.name ? null : table.order.name"
            >
              <Icon name="more" />
            </button>
            <div v-if="menuFor === table.order?.name" class="t-menu" @click.stop>
              <button @click="startMove(table.order)">{{ t('Move to another table') }}</button>
              <button @click="startMerge(table.order)">{{ t('Merge into another order') }}</button>
              <button class="danger" @click="startCancel(table.order)">
                {{ t('Cancel the order') }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="loose.length" class="loose">
          <div class="sub-head">{{ t('Not at a table') }}</div>
          <div class="table-grid">
            <div v-for="order in loose" :key="order.name" class="table-card busy">
              <button class="table-main" @click="openOrder(order.name)">
                <div class="t-head">
                  <span class="t-no small">{{ t(order.order_type) }}</span>
                </div>
                <div class="t-open">
                  <div class="t-total">{{ money(order.total) }}</div>
                  <div class="t-meta">{{ sinceText(order.opened_at) }}</div>
                  <div class="t-meta who">{{ order.customer_name || order.opened_by_name }}</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- open a table: how many are sitting down -->
    <div v-if="opening" class="modal-backdrop" @click.self="opening = null">
      <div class="modal" style="width: 360px">
        <div class="modal-header">
          <Icon name="person" />
          {{ opening.table ? t('Table {no}', { no: opening.table.table_no }) : t(opening.type) }}
          <button class="btn-ghost" @click="opening = null"><Icon name="close" /></button>
        </div>
        <div class="modal-body form">
          <label class="field-label">{{ t('Guests') }}</label>
          <input ref="guestsInput" type="number" min="0" v-model.number="guests" @keyup.enter="confirmOpen" />
          <label class="field-label">{{ t('Note') }}</label>
          <input v-model="note" :placeholder="t('Anything the kitchen or the next cashier should know')" />
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="opening = null">{{ t('Cancel') }}</button>
          <button class="btn btn-primary" :disabled="busy" @click="confirmOpen">
            {{ busy ? t('Working…') : t('Start the order') }}
          </button>
        </div>
      </div>
    </div>

    <!-- move / merge / cancel -->
    <div v-if="action" class="modal-backdrop" @click.self="action = null">
      <div class="modal" style="width: 380px">
        <div class="modal-header">
          {{ actionTitle }}
          <button class="btn-ghost" @click="action = null"><Icon name="close" /></button>
        </div>
        <div class="modal-body form">
          <template v-if="action.kind === 'move'">
            <p class="muted small">{{ t('Pick where it goes. Only free tables are listed.') }}</p>
            <select v-model="targetTable">
              <option :value="null">{{ t('Off the floor (takeaway counter)') }}</option>
              <option v-for="table in freeTables" :key="table.name" :value="table.name">
                {{ table.area }} {{ table.table_no }}
              </option>
            </select>
          </template>
          <template v-else-if="action.kind === 'merge'">
            <p class="muted small">
              {{ t('Everything on this order moves onto the one you pick, and this one is marked merged.') }}
            </p>
            <select v-model="targetOrder">
              <option :value="null">{{ t('Pick an order') }}</option>
              <option v-for="order in otherOrders" :key="order.name" :value="order.name">
                {{ order.table_label || t(order.order_type) }} · {{ money(order.total) }}
              </option>
            </select>
          </template>
          <template v-else>
            <p class="muted small">
              {{ t('Nothing was paid, so nothing is refunded. Say why, it is the only record there is.') }}
            </p>
            <input v-model="reason" :placeholder="t('Reason')" @keyup.enter="runAction" />
          </template>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="action = null">{{ t('Cancel') }}</button>
          <button
            class="btn"
            :class="action.kind === 'cancel' ? 'btn-danger' : 'btn-primary'"
            :disabled="busy || (action.kind === 'merge' && !targetOrder)"
            @click="runAction"
          >
            {{ busy ? t('Working…') : t('Confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import { call } from '../api'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'
import { money } from '../format'
import { t } from '../i18n'

const router = useRouter()
const session = useSessionStore()
const cart = useCartStore()

const tables = ref([])
const loose = ref([])
const loading = ref(true)
const busy = ref(false)
const area = ref(null)
const menuFor = ref(null)
const opening = ref(null)
const guests = ref(2)
const note = ref('')
const guestsInput = ref(null)
const action = ref(null)
const targetTable = ref(null)
const targetOrder = ref(null)
const reason = ref('')
// The server's clock, so a tablet set to the wrong time still shows the right
// "sitting for".
let clockSkew = 0
const now = ref(Date.now())
let ticker = null
let poll = null

const canOpen = computed(() => session.permissions.can_open_table !== false)
const areas = computed(() => [...new Set(tables.value.map((x) => x.area || ''))])
const shown = computed(() =>
  area.value === null ? tables.value : tables.value.filter((x) => (x.area || '') === area.value)
)
const freeTables = computed(() => tables.value.filter((x) => !x.order))
const otherOrders = computed(() =>
  [...tables.value.map((x) => x.order).filter(Boolean), ...loose.value].filter(
    (o) => o.name !== action.value?.order?.name
  )
)
const actionTitle = computed(() =>
  action.value?.kind === 'move'
    ? t('Move the order')
    : action.value?.kind === 'merge'
      ? t('Merge orders')
      : t('Cancel the order')
)

// Frappe sends "2026-09-23 13:29:18.130238", which is neither ISO nor UTC. Make
// it something Date can read; the skew below cancels the time zone out, because
// both sides are read the same way.
function serverTime(value) {
  if (!value) return 0
  return new Date(String(value).replace(' ', 'T').split('.')[0] + 'Z').getTime()
}

function sinceText(opened) {
  if (!opened) return ''
  const mins = Math.max(0, Math.round((now.value - clockSkew - serverTime(opened)) / 60000))
  if (mins < 60) return t('{n} min', { n: mins })
  return t('{h}h {m}m', { h: Math.floor(mins / 60), m: mins % 60 })
}

async function load() {
  if (session.offline) {
    loading.value = false
    return
  }
  try {
    const data = await call('lumenpos.api.restaurant.get_floor', {
      pos_profile: session.posProfile,
    })
    tables.value = data.tables || []
    loose.value = data.loose || []
    if (data.now) clockSkew = Date.now() - serverTime(data.now)
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    loading.value = false
  }
}

function openTable(table) {
  menuFor.value = null
  if (table.order) return openOrder(table.order.name)
  if (!canOpen.value) return session.notify(t('You are not allowed to open a table order'), true)
  opening.value = { table, type: 'Dine in' }
  guests.value = table.seats || 2
  note.value = ''
  nextTick(() => guestsInput.value?.focus())
}

function startLoose(type) {
  opening.value = { table: null, type }
  guests.value = 0
  note.value = ''
  nextTick(() => guestsInput.value?.focus())
}

async function confirmOpen() {
  busy.value = true
  try {
    const order = await call('lumenpos.api.restaurant.open_order', {
      pos_profile: session.posProfile,
      table: opening.value.table?.name || null,
      order_type: opening.value.type,
      guests: guests.value || 0,
      note: note.value || null,
    })
    opening.value = null
    await cart.openOrder(order)
    router.push('/')
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    busy.value = false
  }
}

async function openOrder(name) {
  menuFor.value = null
  try {
    const order = await call('lumenpos.api.restaurant.get_order', { name })
    await cart.openOrder(order)
    router.push('/')
  } catch (e) {
    session.notify(e.message, true)
  }
}

function startMove(order) {
  menuFor.value = null
  targetTable.value = null
  action.value = { kind: 'move', order }
}
function startMerge(order) {
  menuFor.value = null
  targetOrder.value = null
  action.value = { kind: 'merge', order }
}
function startCancel(order) {
  menuFor.value = null
  reason.value = ''
  action.value = { kind: 'cancel', order }
}

async function runAction() {
  busy.value = true
  try {
    const { kind, order } = action.value
    if (kind === 'move') {
      await call('lumenpos.api.restaurant.move_order', {
        name: order.name,
        table: targetTable.value,
      })
    } else if (kind === 'merge') {
      await call('lumenpos.api.restaurant.merge_orders', {
        source: order.name,
        target: targetOrder.value,
      })
    } else {
      await call('lumenpos.api.restaurant.cancel_order', {
        name: order.name,
        reason: reason.value || null,
      })
    }
    action.value = null
    await load()
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  load()
  ticker = setInterval(() => (now.value = Date.now()), 30000)
  // Another waiter can open, move or pay a table while this screen is up.
  poll = setInterval(load, 15000)
})
onUnmounted(() => {
  clearInterval(ticker)
  clearInterval(poll)
})
</script>

<style scoped>
.floor { flex: 1; display: flex; padding: 14px; overflow: hidden; }
.floor-card { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.floor-head {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.area-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.area-tab {
  border: 1px solid transparent;
  background: transparent;
  border-radius: 999px;
  padding: 7px 14px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
}
.area-tab:hover { color: var(--text); }
.area-tab.active { background: var(--brand); color: #fff; }
.area-tab .count { opacity: 0.7; margin-inline-start: 4px; }
.head-actions { display: flex; gap: 8px; }
.floor-body { flex: 1; overflow: auto; padding: 14px; }
.table-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 12px;
}
.table-card {
  position: relative;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card-bg);
  min-height: 108px;
}
.table-card.busy { border-color: var(--brand); background: rgba(20, 99, 255, 0.06); }
.table-main {
  width: 100%;
  height: 100%;
  min-height: 108px;
  border: 0;
  background: transparent;
  font: inherit;
  text-align: start;
  padding: 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: inherit;
}
.t-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.t-no { font-size: 20px; font-weight: 700; }
.t-no.small { font-size: 14px; font-weight: 600; }
.t-seats { font-size: 12px; color: var(--text-muted); }
.t-free { font-size: 12.5px; color: var(--text-muted); margin-top: auto; }
.t-open { margin-top: auto; display: flex; flex-direction: column; gap: 2px; }
.t-total { font-weight: 700; }
.t-meta { font-size: 12px; color: var(--text-muted); }
.t-meta.who { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.t-more {
  position: absolute;
  top: 6px;
  inset-inline-end: 6px;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
}
.t-more:hover { background: var(--surface-2); }
.t-menu {
  position: absolute;
  top: 34px;
  inset-inline-end: 6px;
  z-index: 5;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  min-width: 190px;
  overflow: hidden;
}
.t-menu button {
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  text-align: start;
  padding: 10px 12px;
  cursor: pointer;
  color: inherit;
}
.t-menu button:hover { background: var(--surface-2); }
.t-menu .danger { color: var(--red); }
.sub-head {
  font-size: 12.25px;
  font-weight: 600;
  color: var(--text-muted);
  margin: 20px 0 8px;
}
.empty { padding: 30px; text-align: center; }
</style>
