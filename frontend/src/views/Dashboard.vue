<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { can, request } from "../api";
import ServiceCard from "../components/ServiceCard.vue";

const route = useRoute();
const containers = ref([]);
const groups = ref([]);
const loading = ref(true);
const error = ref("");
const updated = ref(null);
let timer = null;

async function load() {
  try {
    const [containerData, groupData] = await Promise.all([
      request("/api/v1/containers"),
      request("/api/v1/groups"),
    ]);
    containers.value = containerData.containers || [];
    groups.value = groupData.groups || [];
    error.value = "";
    updated.value = new Date();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    loading.value = false;
  }
}

const filtered = computed(() => {
  const text = String(route.query.q || "").trim().toLowerCase();
  if (!text) return containers.value;
  return containers.value.filter(
    (item) => item.name.toLowerCase().includes(text) || item.image.toLowerCase().includes(text),
  );
});

const sections = computed(() => {
  const result = [];
  for (const group of groups.value) {
    const items = filtered.value.filter((item) => item.group && item.group.id === group.id);
    if (items.length) result.push({ title: group.name, items });
  }
  const ungrouped = filtered.value.filter((item) => !item.group);
  if (ungrouped.length) result.push({ title: "Без группы", items: ungrouped });
  return result;
});

const running = computed(() => containers.value.filter((item) => item.state === "running").length);

onMounted(() => {
  load();
  timer = setInterval(load, 10000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <header class="page-head">
    <div>
      <h1>Обзор</h1>
      <p class="sub">Сервисы на этом хосте</p>
    </div>
    <div class="head-actions">
      <span class="muted">{{ running }} из {{ containers.length }} работают</span>
      <button class="ghost" @click="load">Обновить</button>
    </div>
  </header>

  <p v-if="updated" class="muted">обновлено {{ updated.toLocaleTimeString("ru-RU") }}</p>

  <div v-if="error" class="state error">
    <strong>Docker недоступен</strong>
    <p>{{ error }}</p>
  </div>

  <div v-else-if="loading && !containers.length" class="state">Загрузка…</div>

  <div v-else-if="!containers.length" class="state">
    Сервисов пока нет.
    <RouterLink v-if="can('manage')" to="/install">Установить первый</RouterLink>
  </div>

  <div v-else>
    <section v-for="section in sections" :key="section.title" class="group">
      <h2 class="group-title">
        {{ section.title }} <span class="group-count">{{ section.items.length }}</span>
      </h2>
      <div class="grid">
        <ServiceCard
          v-for="item in section.items"
          :key="item.id"
          :item="item"
          @refresh="load"
        />
      </div>
    </section>
  </div>
</template>
