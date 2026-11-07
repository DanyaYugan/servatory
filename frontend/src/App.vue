<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { authChecked, can, checkAuth, request, user } from "./api";
import Login from "./views/Login.vue";
import SetupWizard from "./components/SetupWizard.vue";

const route = useRoute();
const router = useRouter();
const profile = ref(null);

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

const panelName = computed(() => (profile.value && profile.value.panel_name) || "Servatory");

async function loadProfile() {
  try {
    profile.value = await request("/api/v1/system/profile");
  } catch {
    profile.value = { onboarded: true, panel_name: "Servatory", public_url: "" };
  }
  if (profile.value && profile.value.panel_name) {
    document.title = `${profile.value.panel_name} — Servatory`;
  }
}

function finishSetup() {
  profile.value = { ...(profile.value || {}), onboarded: true };
}

watch(
  user,
  (value) => {
    if (value) loadProfile();
    else profile.value = null;
  },
  { immediate: true },
);

onMounted(checkAuth);
</script>

<template>
  <div v-if="!authChecked" class="center">Проверка входа…</div>

  <Login v-else-if="!user" />

  <div v-else class="shell">
    <SetupWizard
      v-if="profile && !profile.onboarded"
      :initial="profile"
      @done="finishSetup"
    />

    <header class="topbar">
      <RouterLink to="/" class="logo">
        <span class="logo-mark">S</span>
        <span>{{ panelName }}</span>
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
