<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { can, request } from "../api";

const state = reactive({ domain: "", email: "", enabled: false });
const status = ref(null);
const error = ref("");
const message = ref("");
const busy = ref(false);
const canManage = computed(() => can("manage"));

async function load() {
  try {
    const data = await request("/api/v1/system/tls");
    status.value = data;
    state.domain = data.domain || "";
    state.email = data.email || "";
    state.enabled = Boolean(data.enabled);
    error.value = "";
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function save() {
  busy.value = true;
  error.value = "";
  message.value = "";
  try {
    const data = await request("/api/v1/system/tls", {
      method: "PUT",
      body: JSON.stringify(state),
    });
    status.value = data;
    message.value = data.enabled ? "Caddy запущен, TLS включён" : "TLS выключен";
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
    <div class="form-grid">
      <label class="field">
        <span>Домен</span>
        <input v-model="state.domain" placeholder="panel.example.com" />
      </label>
      <label class="field">
        <span>Почта для Let's Encrypt</span>
        <input v-model="state.email" placeholder="admin@example.com" />
      </label>
      <label class="field">
        <span>TLS включён</span>
        <select v-model="state.enabled">
          <option :value="true">да</option>
          <option :value="false">нет</option>
        </select>
      </label>
    </div>

    <p class="muted" style="margin-top: 12px">
      Панель поднимает Caddy рядом с собой. Нужны свободные порты 80 и 443,
      а домен должен указывать на этот сервер. Панель остаётся доступна
      напрямую на 8090 — это запасной вход.
    </p>

    <div v-if="status" class="props" style="margin-top: 14px">
      <div>Адрес: {{ status.url || "не задан" }}</div>
      <div v-if="status.container">
        Caddy:
        {{ status.container.running ? "работает" : "остановлен" }}
        <span v-if="status.container.error"> · {{ status.container.error }}</span>
      </div>
      <div v-else>Caddy: контейнер ещё не создан</div>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="message" class="muted">{{ message }}</p>

    <div class="form-actions">
      <button v-if="canManage" class="primary" :disabled="busy" @click="save">
        {{ busy ? "Применяю…" : "Применить" }}
      </button>
      <button class="ghost" @click="load">Обновить статус</button>
    </div>
  </div>
</template>
