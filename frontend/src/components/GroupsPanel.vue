<script setup>
import { onMounted, ref } from "vue";

import { request } from "../api";

const groups = ref([]);
const name = ref("");
const error = ref("");

async function load() {
  try {
    const data = await request("/api/v1/groups");
    groups.value = data.groups || [];
    error.value = "";
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function create() {
  if (!name.value.trim()) return;
  try {
    await request("/api/v1/groups", {
      method: "POST",
      body: JSON.stringify({ name: name.value.trim() }),
    });
    name.value = "";
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function rename(group) {
  const value = window.prompt("Новое имя группы", group.name);
  if (!value || value.trim() === group.name) return;
  try {
    await request(`/api/v1/groups/${group.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name: value.trim() }),
    });
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function remove(group) {
  if (!window.confirm(`Удалить группу «${group.name}»? Сервисы останутся без группы.`)) return;
  try {
    await request(`/api/v1/groups/${group.id}`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function move(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= groups.value.length) return;
  const ids = groups.value.map((group) => group.id);
  [ids[index], ids[target]] = [ids[target], ids[index]];
  try {
    await request("/api/v1/groups/reorder", {
      method: "POST",
      body: JSON.stringify({ ids }),
    });
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="head-actions" style="margin-bottom: 12px">
      <input v-model="name" placeholder="Новая группа" @keydown.enter="create" />
      <button class="primary" @click="create">Создать</button>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>

    <ul v-if="groups.length" class="list">
      <li v-for="(group, index) in groups" :key="group.id">
        <div class="left"><span>{{ group.name }}</span></div>
        <div class="head-actions">
          <button class="mini" :disabled="index === 0" @click="move(index, -1)">↑</button>
          <button class="mini" :disabled="index === groups.length - 1" @click="move(index, 1)">↓</button>
          <button class="mini" @click="rename(group)">Переименовать</button>
          <button class="mini danger" @click="remove(group)">Удалить</button>
        </div>
      </li>
    </ul>
    <p v-else class="muted">Групп пока нет. Сервисы живут в разделе «Без группы».</p>
  </div>
</template>
