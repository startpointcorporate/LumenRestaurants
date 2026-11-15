<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="linkpay card" aria-label="Link Pay">
    <template v-if="link.attempt && !['Cancelled','Completed'].includes(link.attempt.state)">
      <h3>Link Pay · {{ money(link.attempt.amount, link.attempt.currency) }}</h3>
      <p role="status">{{ labels[link.attempt.state] }}</p>
      <p v-if="link.attempt.state === 'Paid'">{{ t('Payment received. Cashier finalization is required.') }}</p>
      <p>{{ t('This order is locked until Link Pay is cancelled or finalized.') }}</p>
      <template v-if="url">
        <input readonly :value="url" :aria-label="t('Payment link')" @focus="$event.target.select()" />
        <div class="linkpay-actions">
          <a :href="url" target="_blank" rel="noopener noreferrer">{{ t('Open payment link') }}</a>
          <button class="btn btn-outline" @click="copy">{{ t('Copy link') }}</button>
          <a :href="sms">SMS</a><a :href="email">{{ t('Email') }}</a>
          <a :href="whatsapp" target="_blank" rel="noopener noreferrer">WhatsApp</a>
        </div>
      </template>
      <div class="linkpay-actions">
        <button class="btn btn-outline" :disabled="link.busy || session.offline" @click="refresh">{{ t('Refresh Link Pay') }}</button>
        <button v-if="link.attempt.canCancel" class="btn btn-outline" :disabled="link.busy || session.offline" @click="cancel">{{ t('Cancel Link Pay') }}</button>
        <button v-if="link.attempt.canFinalize" class="btn btn-primary" :disabled="link.busy || session.offline" @click="finalize">{{ t('Finalize sale') }}</button>
      </div>
    </template>
    <template v-else>
      <button class="btn btn-outline" :disabled="Boolean(blocked) || link.busy || link.checking" @click="prepare">Link Pay</button>
      <p v-if="blocked" class="muted">{{ blocked }}</p>
    </template>
    <template v-if="link.uncertain">
      <p role="status">{{ t('The payment result is uncertain. Keep this attempt and refresh before taking another payment.') }}</p>
      <button class="btn btn-outline" :disabled="link.busy || session.offline" @click="refresh">{{ t('Refresh Link Pay') }}</button>
      <button v-if="cart.lines.length" class="btn btn-outline" :disabled="link.busy || session.offline" @click="prepare">{{ t('Retry the same Link Pay attempt') }}</button>
    </template>
    <p v-if="link.error" role="alert">{{ t('Unable to refresh Link Pay. Keep this attempt and try again.') }}</p>
  </section>
</template>
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { call } from '../api'
import { useCartStore } from '../stores/cart'
import { useLinkPayStore } from '../stores/linkpay'
import { useSessionStore } from '../stores/session'
import { money } from '../format'
import { t } from '../i18n'
const props = defineProps({ payments: { type:Array,default:()=>[] }, redeemPoints:{type:Number,default:0}, quoteReady:Boolean })
const emit=defineEmits(['posted'])
let alive=true
onUnmounted(()=>{alive=false})
const cart=useCartStore(), link=useLinkPayStore(), session=useSessionStore(), posted=ref(null)
const labels=computed(()=>({Prepared:t('Waiting for Link Pay payment'),Claimed:t('Link Pay payment is processing'),Paid:t('Payment received'),Review:t('Link Pay requires reconciliation')}))
const blocked=computed(()=>{
  if(session.offline) return t('Link Pay requires a connection.')
  if(!link.available) return t('Link Pay is not enabled for this outlet yet.')
  if(cart.exchange || cart.saleCurrency.foreign || props.redeemPoints || props.payments.some(p=>p.card_no || !link.cashModes.includes(p.mode_of_payment))) return t('Link Pay supports cash only alongside it. Remove other payments and loyalty points first.')
  if(!props.quoteReady) return t('A server quote is required for Link Pay.')
  return ''
})
const url=computed(()=>{try{const u=new URL(link.attempt?.url);return u.protocol==='https:'&&!u.username&&!u.password?u.href:''}catch{return ''}})
const text=computed(()=>`Link Pay : ${url.value}`)
const sms=computed(()=>`sms:${/iPad|iPhone|iPod/.test(navigator.userAgent)?'&':'?'}body=${encodeURIComponent(text.value)}`)
const email=computed(()=>`mailto:?subject=Link%20Pay&body=${encodeURIComponent(text.value)}`)
const whatsapp=computed(()=>`https://wa.me/?text=${encodeURIComponent(text.value)}`)
async function copy(){try{await navigator.clipboard.writeText(url.value)}catch{session.notify(t('Select and copy the payment link.'),true)}}
async function canonical(value){
  if(!alive)return
  if(value?.state==='Completed' && value.receipt && posted.value!==value.attempt){posted.value=value.attempt;cart.acceptPostedReceipt(value.receipt,value.attempt);emit('posted',value.receipt);return}
  if(value?.order && cart.order?.name!==value.order){
    cart.bindLinkPayOrder({name:value.order})
    const generation=link.generation
    const order=await call('lumen_restaurants.api.restaurant.get_order',{name:value.order})
    if(!alive||generation!==link.generation)return
    await cart.openOrder(order)
  }
  if(value?.state==='Paid' && value.canFinalize && session.registerSession?.name && !link.busy) await finalize()
}
async function prepare(){
  if(link.busy || (blocked.value && !link.uncertain)) return
  try{
    if(!link.locked && cart.order) { await cart.saveOrder(); await link.context(cart.order.name) }
    const payload={...cart._basePayload(),cart:cart.orderSnapshot(),payments:props.payments.map(p=>({...p})),order:cart.order?.name||null,discount_passcode:cart.discountPasscode,discount_request:cart.discountRequest}
    await canonical(await link.prepare(payload,cart.order?.name))
  }catch{link.error=true}
}
async function refresh(){try{await canonical(await link.refresh(cart.order?.name))}catch{link.error=true}}
async function cancel(){try{await canonical(await link.mutate('cancel'))}catch{link.error=true}}
async function finalize(){try{const value=await link.mutate('finalize');if(value?.state==='Completed')await canonical(value)}catch{link.error=true}}
onMounted(async()=>{if(session.offline){link.available=false;return}try{if(link.orderName===cart.order?.name&&link.attempt)await canonical(await link.refresh(cart.order?.name));else await canonical(await link.context(cart.order?.name,link.uncertain&&link.basketSignature===JSON.stringify(cart.orderSnapshot())?link.requestKey:null))}catch{link.error=true}})
</script>
<style scoped>.linkpay{padding:16px;margin:14px 0}.linkpay input{width:100%;box-sizing:border-box}.linkpay-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px}.linkpay-actions a{padding:8px}</style>
