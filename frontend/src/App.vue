<template>
  <router-view />
</template>

<script setup>
import { watch } from 'vue'
import { useApp } from './store'

const store = useApp()
watch(
  () => store.site.name,
  () => { document.title = `${store.site.name} · ${store.site.app || 'DataLoom'}` }
)
</script>
