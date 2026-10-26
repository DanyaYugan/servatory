<script setup>
import { onMounted, ref } from "vue";

import { request } from "../api";

const items = ref([]);
const error = ref("");

async function load() {
  try {
    const data = await request("/api/v1/audit?limit=200");
    items.value = data.items || [];
    error.value = "";
  } catch (err) {
    error.value = String(err.message || err);
  }
}

function when(value) {
  return new Date(value * 1000).toLocaleString("ru-RU");
}

onMounted(load);
</script>

<template>
  <div>
    <div class="head-actions" style="margin-bottom: 12px">
      <button class="ghost" @click="load">Обновить</button>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>
    <table v-if="items.length" class="props">
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td style="width: 160px">{{ when(item.at) }}</td>
          <td style="width: 120px">{{ item.login }}</td>
          <td style="width: 150px">{{ item.action }}</td>
          <td>{{ item.object }}</td>
          <td style="width: 90px">{{ item.result }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="muted">Записей пока нет.</p>
  </div>
</template>
