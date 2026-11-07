<script setup>
import { reactive, ref } from "vue";

import { request } from "../api";

const props = defineProps({
  initial: { type: Object, required: true },
  skipLabel: { type: String, default: "Пропустить" },
  showSkip: { type: Boolean, default: true },
});
const emit = defineEmits(["saved", "skip"]);

const form = reactive({
  panel_name: props.initial.panel_name || "Servatory",
  public_url: props.initial.public_url || "",
});
const error = ref("");
const busy = ref(false);

async function save() {
  busy.value = true;
  error.value = "";
  try {
    const data = await request("/api/v1/system/profile", {
      method: "PATCH",
      body: JSON.stringify({ ...form, onboarded: true }),
    });
    emit("saved", data);
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}

async function skip() {
  try {
    await request("/api/v1/system/profile", {
      method: "PATCH",
      body: JSON.stringify({ ...form, onboarded: true }),
    });
  } catch {
    // пропуск не должен блокировать вход
  }
  emit("skip");
}
</script>

<template>
  <div>
    <div class="form-grid">
      <label class="field">
        <span>Название панели</span>
        <input v-model="form.panel_name" placeholder="Servatory" />
      </label>
      <label class="field">
        <span>Публичный адрес</span>
        <input v-model="form.public_url" placeholder="https://panel.example.com" />
      </label>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>

    <div class="form-actions">
      <button class="primary" :disabled="busy" @click="save">
        {{ busy ? "Сохраняю…" : "Сохранить" }}
      </button>
      <button v-if="showSkip" class="ghost" @click="skip">{{ skipLabel }}</button>
    </div>
  </div>
</template>
