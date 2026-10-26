<script setup>
import { ref } from "vue";

import { logout, request, user } from "../api";

const current = ref("");
const password = ref("");
const confirm = ref("");
const error = ref("");
const message = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  message.value = "";
  if (password.value.length < 6) {
    error.value = "пароль не короче 6 символов";
    return;
  }
  if (password.value !== confirm.value) {
    error.value = "пароли не совпадают";
    return;
  }
  busy.value = true;
  try {
    await request("/api/v1/auth/password", {
      method: "POST",
      body: JSON.stringify({ current: current.value, password: password.value }),
    });
    message.value = "Пароль изменён. Войдите заново.";
    await logout();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div>
    <table class="props">
      <tbody>
        <tr><td>Логин</td><td>{{ user ? user.login : "—" }}</td></tr>
        <tr><td>Роль</td><td>{{ user ? user.role : "—" }}</td></tr>
        <tr><td>Смена роли</td><td class="muted">свою роль изменить нельзя, только другой superadmin</td></tr>
      </tbody>
    </table>

    <h3 style="margin-top: 22px">Сменить пароль</h3>
    <div class="form-grid" style="margin-top: 10px">
      <label class="field">
        <span>Текущий пароль</span>
        <input v-model="current" type="password" autocomplete="current-password" />
      </label>
      <label class="field">
        <span>Новый пароль</span>
        <input v-model="password" type="password" autocomplete="new-password" />
      </label>
      <label class="field">
        <span>Повторите новый</span>
        <input v-model="confirm" type="password" autocomplete="new-password" />
      </label>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="message" class="muted">{{ message }}</p>

    <div class="form-actions">
      <button class="primary" :disabled="busy" @click="submit">
        {{ busy ? "Меняю…" : "Сменить пароль" }}
      </button>
    </div>
  </div>
</template>
