<template>
  <img :src="src" :width="size" :height="size" alt="Logo" class="dc-logo" />
</template>

<script setup>
import { computed } from 'vue'
import { useApp } from '@/store'

defineProps({ size: { type: [Number, String], default: 34 } })

const store = useApp()
const src = computed(() => store.site.logo || '/favicon.svg')
</script>

<style scoped>
.dc-logo { flex: none; display: block; object-fit: contain; }
</style>
