<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
 <div v-if="cart.linkPayLocked || orders.length || pending.length" class="card linkpay-resume">
  <p v-if="cart.linkPayLocked">{{ link.checking ? t('Checking…') : t('This order is locked until Link Pay is cancelled or finalized.') }}</p>
  <button v-if="cart.linkPayLocked" class="btn btn-primary" @click="$emit('resume')">{{ t('Resume Link Pay') }}</button>
  <template v-else>
   <button v-for="order in orders" :key="order" class="btn btn-outline" :disabled="busy || session.offline || (cart.lines.length > 0 && cart.order?.name !== order)" @click="resume(order)">{{ t('Resume Link Pay') }} · {{ order }}</button>
   <button v-for="key in pending" :key="key" class="btn btn-outline" :disabled="busy || session.offline || cart.lines.length > 0" @click="resume(null,key)">{{ t('Recover Link Pay attempt') }}</button>
  </template>
 </div>
</template>
<script setup>
import {computed,ref} from 'vue'
import {call} from '../api'
import {useCartStore} from '../stores/cart'
import {useLinkPayStore} from '../stores/linkpay'
import {useSessionStore} from '../stores/session'
import {t} from '../i18n'
const link=useLinkPayStore(),cart=useCartStore(),session=useSessionStore(),busy=ref(false)
const emit=defineEmits(['resume'])
const orders=computed(()=>{link.attempt;link.requestKey;return link.savedOrders()}),pending=computed(()=>{link.attempt;link.requestKey;return link.pendingKeys()})
async function resume(order,key=null){
 if(busy.value||(cart.lines.length&&cart.order?.name!==order))return
 const snapshot=JSON.stringify(cart.orderSnapshot()),priorOrder=cart.order?.name||null
 busy.value=true
 try{const a=await link.context(order,key),generation=link.generation
  if(a?.order&&cart.order?.name!==a.order){const doc=await call('lumen_restaurants.api.restaurant.get_order',{name:a.order});if(generation!==link.generation||JSON.stringify(cart.orderSnapshot())!==snapshot||(cart.order?.name||null)!==priorOrder)return;await cart.openOrder(doc)}
  emit('resume')
 }catch{session.notify(t('Unable to refresh Link Pay. Keep this attempt and try again.'),true)}finally{busy.value=false}}
</script>
<style scoped>.linkpay-resume{padding:18px;margin:12px}.linkpay-resume button{margin:4px}</style>
