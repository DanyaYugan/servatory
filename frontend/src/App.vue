<script setup>
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

import { authChecked, can, checkAuth, user } from "./api";
import Login from "./views/Login.vue";

const route = useRoute();
const router = useRouter();

const search = computed({
  get: () => String(route.query.q || ""),
  set: (value) => {
    const query = { ...route.query };
    if (value) query.q = value;
    else delete query.q;
    if (route.name === "dashboard") router.replace({ query });
    else router.push({ path: "/", query });
  },
});

onMounted(checkAuth);
</script>

<template>
  <div v-if="!authChecked" class="center">Проверка входа…</div>

  <Login v-else-if="!user" />

  <div v-else class="shell">
    <header class="topbar">
      <RouterLink to="/" class="logo">
        <span class="logo-mark">S</span>
        <span>Servatory</span>
      </RouterLink>

      <div class="widgets">
        <input
          v-model="search"
          class="widget-search"
          placeholder="Поиск сервисов по имени или образу"
        />
      </div>

      <div class="top-actions">
        <RouterLink v-if="can('manage')" to="/install" class="top-btn">
          <span class="top-icon">＋</span>
          <span>Добавление</span>
        </RouterLink>
        <RouterLink to="/settings" class="top-btn">
          <span class="top-icon">⚙</span>
          <span>Настройки</span>
        </RouterLink>
      </div>
    </header>

    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>
