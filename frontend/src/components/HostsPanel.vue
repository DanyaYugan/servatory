<script setup>
import { onMounted, ref } from "vue";

import { request } from "../api";

const containers = ref([]);
const error = ref("");

onMounted(async () => {
  try {
    const data = await request("/api/v1/containers");
    containers.value = data.containers || [];
  } catch (err) {
    error.value = String(err.message || err);
  }
});
</script>

<template>
  <div>
    <table class="props">
      <tbody>
        <tr><td>Состояние</td><td>{{ error ? "нет связи" : "подключён" }}</td></tr>
        <tr><td>Docker</td><td>локальный сокет</td></tr>
        <tr><td>Сервисов</td><td>{{ containers.length }}</td></tr>
      </tbody>
    </table>
    <p v-if="error" class="form-error">{{ error }}</p>
    <p class="muted" style="margin-top: 12px">Удалённые хосты появятся в 0.3.0.</p>
  </div>
</template>
