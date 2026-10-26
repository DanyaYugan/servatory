<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { can, logout, request, user, version } from "../api";
import GroupsPanel from "../components/GroupsPanel.vue";
import HostsPanel from "../components/HostsPanel.vue";
import SecurityPanel from "../components/SecurityPanel.vue";
import TlsPanel from "../components/TlsPanel.vue";
import UsersPanel from "../components/UsersPanel.vue";
import AuditPanel from "../components/AuditPanel.vue";

const route = useRoute();
const router = useRouter();
const tab = ref(String(route.query.tab || "general"));

function setTab(name) {
  tab.value = name;
  router.replace({ query: { ...route.query, tab: name } });
}
const meta = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    meta.value = await request("/api/v1/meta");
  } catch (err) {
    error.value = String(err.message || err);
  }
});
</script>

<template>
  <header class="page-head">
    <div>
      <h1>Настройки</h1>
      <p class="sub">Панель, группы и хосты</p>
    </div>
  </header>

  <div class="tabs">
    <button :class="{ active: tab === 'general' }" @click="setTab('general')">Общие</button>
    <button :class="{ active: tab === 'security' }" @click="setTab('security')">Безопасность</button>
    <button :class="{ active: tab === 'tls' }" @click="setTab('tls')">Домены и TLS</button>
    <button :class="{ active: tab === 'groups' }" @click="setTab('groups')">Группы</button>
    <button :class="{ active: tab === 'hosts' }" @click="setTab('hosts')">Хосты</button>
    <button v-if="can('users')" :class="{ active: tab === 'users' }" @click="setTab('users')">Пользователи</button>
    <button v-if="can('audit')" :class="{ active: tab === 'audit' }" @click="setTab('audit')">Журнал</button>
  </div>

  <section v-if="tab === 'general'" class="form">
    <h2>О системе</h2>
    <table class="props">
      <tbody>
        <tr><td>Версия</td><td>{{ version }}</td></tr>
        <tr><td>Схема данных</td><td>{{ meta ? meta.schema : "—" }}</td></tr>
        <tr><td>Пользователь</td><td>{{ user ? `${user.login} · ${user.role}` : "—" }}</td></tr>
        <tr><td>Конфигурация</td><td>/data/config.toml</td></tr>
        <tr><td>Данные</td><td>/data/servatory.db</td></tr>
      </tbody>
    </table>
    <p v-if="error" class="form-error">{{ error }}</p>
    <p class="muted" style="margin-top: 12px">
      Редактирование настроек появится позже. Сейчас файл правится на сервере.
    </p>
    <div class="form-actions">
      <button class="ghost" @click="logout">Выйти из панели</button>
    </div>
  </section>

  <section v-else-if="tab === 'security'" class="form">
    <h2>Моя учётная запись</h2>
    <SecurityPanel />
  </section>

  <section v-else-if="tab === 'tls'" class="form">
    <h2>Домены и TLS</h2>
    <TlsPanel />
  </section>

  <section v-else-if="tab === 'groups'" class="form">
    <h2>Группы</h2>
    <GroupsPanel />
  </section>

  <section v-else-if="tab === 'hosts'" class="form">
    <h2>Хосты</h2>
    <HostsPanel />
  </section>

  <section v-else-if="tab === 'users'" class="form">
    <h2>Пользователи</h2>
    <UsersPanel />
  </section>

  <section v-else class="form">
    <h2>Журнал действий</h2>
    <AuditPanel />
  </section>
</template>
