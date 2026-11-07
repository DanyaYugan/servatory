<script setup>
import { onMounted, ref } from "vue";

import { request } from "../api";

const info = ref(null);
const busy = ref(false);
const message = ref("");
const error = ref("");

async function load() {
  try {
    info.value = await request("/api/v1/system/update");
    error.value = "";
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function update() {
  if (!window.confirm("Обновить панель и перезапустить её?")) return;
  busy.value = true;
  message.value = "";
  error.value = "";
  try {
    const data = await request("/api/v1/system/update", { method: "POST" });
    message.value = data.message;
    window.setTimeout(() => window.location.reload(), 15000);
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <p v-if="info" class="muted">
      Версия: {{ info.version }}
      <span v-if="info.image"> · образ {{ info.image }}</span>
    </p>
    <p v-if="info && !info.compose" class="muted">
      Панель запущена не через compose. Обновление: <code>docker compose up -d --build</code>.
    </p>
    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="message" class="muted">{{ message }}</p>
    <div class="form-actions">
      <button
        class="primary"
        :disabled="busy || (info && !info.compose)"
        @click="update"
      >
        {{ busy ? "Запускаю…" : "Обновить панель" }}
      </button>
    </div>
  </div>
</template>
