<script setup>
import { ref } from "vue";

import { login } from "../api";

const name = ref("admin");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    await login(name.value.trim(), password.value);
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <section class="login">
      <h1>Servatory</h1>
      <p class="sub">Вход в панель</p>

      <label class="field">
        <span>Логин</span>
        <input v-model="name" autocomplete="username" />
      </label>

      <label class="field">
        <span>Пароль</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          @keydown.enter="submit"
        />
      </label>

      <p v-if="error" class="form-error">{{ error }}</p>

      <button class="primary" :disabled="loading" @click="submit">
        {{ loading ? "Вхожу…" : "Войти" }}
      </button>
    </section>
  </div>
</template>
