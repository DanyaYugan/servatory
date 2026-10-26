<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { request } from "../api";

const router = useRouter();

const mode = ref("form");
const form = reactive({
  name: "", image: "", ports: "", volumes: "", env: "", restart: "unless-stopped",
});
const yaml = ref("");
const error = ref("");
const installing = ref(false);
const results = ref([]);
const tags = ref([]);
const repo = ref("");
const showResults = ref(false);
let searchTimer = null;

function lines(text) {
  return text.split("\n").map((line) => line.trim()).filter(Boolean);
}

function parseEnv(text) {
  const env = {};
  for (const line of lines(text)) {
    const index = line.indexOf("=");
    if (index <= 0) throw new Error(`переменная должна быть KEY=VALUE: ${line}`);
    env[line.slice(0, index).trim()] = line.slice(index + 1).trim();
  }
  return env;
}

function onImageInput(value) {
  form.image = value;
  if (searchTimer) clearTimeout(searchTimer);
  if (value.trim().length < 2) {
    showResults.value = false;
    return;
  }
  searchTimer = setTimeout(async () => {
    try {
      const data = await request(`/api/v1/images/search?q=${encodeURIComponent(value.trim())}`);
      results.value = data.results || [];
      showResults.value = true;
    } catch {
      showResults.value = false;
    }
  }, 300);
}

async function selectImage(item) {
  form.image = item.name;
  repo.value = item.name;
  showResults.value = false;
  tags.value = [];
  try {
    const data = await request(`/api/v1/images/tags?name=${encodeURIComponent(item.name)}`);
    tags.value = data.tags || [];
  } catch {
    tags.value = [];
  }
  try {
    const data = await request(`/api/v1/images/details?name=${encodeURIComponent(item.name)}`);
    const hints = data.hints || {};
    if (!form.ports.trim() && hints.ports?.length) form.ports = hints.ports.join("\n");
    if (!form.volumes.trim() && hints.volumes?.length) form.volumes = hints.volumes.join("\n");
    if (!form.env.trim() && hints.env && Object.keys(hints.env).length) {
      form.env = Object.entries(hints.env).map(([key, value]) => `${key}=${value}`).join("\n");
    }
  } catch {
    // подсказок нет
  }
}

function applyTag(tag) {
  if (repo.value) form.image = `${repo.value}:${tag}`;
}

async function submit() {
  installing.value = true;
  error.value = "";
  try {
    if (mode.value === "yaml") {
      const data = await request("/api/v1/containers/compose", {
        method: "POST",
        body: JSON.stringify({ yaml: yaml.value }),
      });
      const name = data.container ? data.container.name : "";
      router.push(name ? `/services/${encodeURIComponent(name)}` : "/");
      return;
    }
    const data = await request("/api/v1/containers", {
      method: "POST",
      body: JSON.stringify({
        name: form.name.trim(),
        image: form.image.trim(),
        ports: lines(form.ports),
        volumes: lines(form.volumes),
        env: parseEnv(form.env),
        restart: form.restart,
      }),
    });
    const name = data.container ? data.container.name : form.name.trim();
    router.push(`/services/${encodeURIComponent(name)}`);
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    installing.value = false;
  }
}
</script>

<template>
  <header class="page-head">
    <div>
      <h1>Установка</h1>
      <p class="sub">Новый сервис на этом хосте</p>
    </div>
    <div class="head-actions">
      <button class="ghost" :class="{ primary: mode === 'form' }" @click="mode = 'form'">Форма</button>
      <button class="ghost" :class="{ primary: mode === 'yaml' }" @click="mode = 'yaml'">YAML</button>
    </div>
  </header>

  <section class="form">
    <div v-if="mode === 'form'" class="form-grid">
      <label class="field">
        <span>Имя</span>
        <input v-model="form.name" placeholder="my-service" />
      </label>

      <label class="field">
        <span>Образ</span>
        <input
          :value="form.image"
          placeholder="nginx:alpine"
          autocomplete="off"
          @input="onImageInput($event.target.value)"
        />
        <div v-if="showResults && results.length" class="results">
          <button
            v-for="item in results"
            :key="item.name"
            type="button"
            class="result"
            @click="selectImage(item)"
          >
            <strong>{{ item.name }}</strong>
            <span>{{ item.stars }} ★ · {{ item.pulls }} загрузок</span>
            <em v-if="item.official">official</em>
            <small v-if="item.description">{{ item.description }}</small>
          </button>
        </div>
        <select v-if="tags.length" @change="applyTag($event.target.value)">
          <option value="latest">latest</option>
          <option v-for="tag in tags" :key="tag" :value="tag">{{ tag }}</option>
        </select>
      </label>

      <label class="field">
        <span>Порты (по одному в строке)</span>
        <textarea v-model="form.ports" rows="3" placeholder="8081:80/tcp" />
      </label>

      <label class="field">
        <span>Тома (по одному в строке)</span>
        <textarea v-model="form.volumes" rows="3" placeholder="data:/data" />
      </label>

      <label class="field">
        <span>Переменные (KEY=VALUE)</span>
        <textarea v-model="form.env" rows="3" placeholder="TZ=Asia/Yekaterinburg" />
      </label>

      <label class="field">
        <span>Перезапуск</span>
        <select v-model="form.restart">
          <option value="unless-stopped">unless-stopped</option>
          <option value="always">always</option>
          <option value="no">no</option>
          <option value="on-failure">on-failure</option>
        </select>
      </label>
    </div>

    <label v-else class="field">
      <span>docker-compose YAML</span>
      <textarea v-model="yaml" rows="14" placeholder="services:&#10;  app:&#10;    image: nginx:alpine&#10;    ports:&#10;      - 8084:80" />
    </label>

    <p v-if="error" class="form-error">{{ error }}</p>

    <div class="form-actions">
      <button class="primary" :disabled="installing" @click="submit">
        {{ installing ? "Устанавливаю…" : "Установить" }}
      </button>
      <RouterLink to="/" class="ghost">Отмена</RouterLink>
    </div>
  </section>
</template>
