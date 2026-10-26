<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { request, user as currentUser } from "../api";

const users = ref([]);
const error = ref("");
const form = reactive({ login: "", password: "", role: "viewer" });
const roles = ["superadmin", "admin", "operator", "viewer"];
const others = computed(() =>
  users.value.filter((user) => user.login !== (currentUser.value ? currentUser.value.login : "")),
);

async function load() {
  try {
    const data = await request("/api/v1/users");
    users.value = data.users || [];
    error.value = "";
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function create() {
  try {
    await request("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(form),
    });
    form.login = "";
    form.password = "";
    form.role = "viewer";
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function changeRole(user, role) {
  try {
    await request(`/api/v1/users/${user.id}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function resetPassword(user) {
  const password = window.prompt(`Новый пароль для ${user.login} (не короче 6 символов)`);
  if (!password) return;
  try {
    await request(`/api/v1/users/${user.id}`, {
      method: "PATCH",
      body: JSON.stringify({ password }),
    });
    window.alert("Пароль изменён");
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function remove(user) {
  if (!window.confirm(`Удалить пользователя ${user.login}?`)) return;
  try {
    await request(`/api/v1/users/${user.id}`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="form-grid" style="margin-bottom: 14px">
      <label class="field">
        <span>Логин</span>
        <input v-model="form.login" placeholder="operator" />
      </label>
      <label class="field">
        <span>Пароль</span>
        <input v-model="form.password" type="password" placeholder="не короче 6 символов" />
      </label>
      <label class="field">
        <span>Роль</span>
        <select v-model="form.role">
          <option v-for="role in roles" :key="role" :value="role">{{ role }}</option>
        </select>
      </label>
      <div class="field">
        <span>&nbsp;</span>
        <button class="primary" @click="create">Создать</button>
      </div>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>

    <p class="muted" style="margin-bottom: 10px">
      Своя учётная запись — в разделе «Безопасность». Здесь другие пользователи.
    </p>

    <ul v-if="others.length" class="list">
      <li v-for="user in others" :key="user.id">
        <div class="left">
          <span>{{ user.login }}</span>
          <small>{{ new Date(user.created_at * 1000).toLocaleDateString("ru-RU") }}</small>
        </div>
        <div class="head-actions">
          <select :value="user.role" @change="changeRole(user, $event.target.value)">
            <option v-for="role in roles" :key="role" :value="role">{{ role }}</option>
          </select>
          <button class="mini" @click="resetPassword(user)">Пароль</button>
          <button class="mini danger" @click="remove(user)">Удалить</button>
        </div>
      </li>
    </ul>
    <p v-else class="muted">Других пользователей нет.</p>
  </div>
</template>
