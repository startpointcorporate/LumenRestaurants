<template>
  <p role="status" class="muted small">
    {{ t(message) }}
    <button v-if="!session.offline && !cart.quotePending" class="btn btn-outline" @click="cart.quote()">
      {{ t('Retry') }}
    </button>
  </p>
</template>

<script setup>
import { computed } from 'vue'
import { t } from '../i18n'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const cart = useCartStore()
const session = useSessionStore()
const message = computed(() => {
  if (session.offline) return cart.canPriceOffline ? 'Provisional total (offline)'
    : 'This basket needs an online tax calculation before payment.'
  if (cart.quotePending) return 'Calculating taxes…'
  if (cart.quoteUnavailable) return 'Unable to verify the sale total.'
  if (cart.quoteExpired) return 'The tax quote has expired.'
  return 'Waiting for a tax quote.'
})
</script>
