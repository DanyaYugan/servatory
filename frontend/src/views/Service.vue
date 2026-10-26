<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { can, request } from "../api";
import {
  containerAction,
  createBackup as createBackupRequest,
  deleteBackup as deleteBackupRequest,
  deleteContainer,
  listBackups,
  loadLogs as loadLogsRequest,
  restoreBackup as restoreBackupRequest,
  saveCheck as saveCheckRequest,
  setGroup,
  setLink,
  updateContainer,
} from "../containers";
import { formatSize, portsText } from "../format";

const props = defineProps({ name: { type: String, required: true } });
const route = useRoute();
const router = useRouter();

const item = ref(null);
const groups = ref([]);
const backups = ref([]);
const tab = ref(route.query.tab || "overview");
const loading = ref(true);
const error = ref("");
const message = ref("");
const busy = ref(false);
const backupBusy = ref(false);
const check = ref(null);
const checkUrl = ref("");
const checkInterval = ref(60);
const checkEnabled = ref(true);
const checkSaving = ref(false);
const logsText = ref("");
const logsBusy = ref(false);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [detail, groupData] = await Promise.all([
      request(`/api/v1/containers/${encodeURIComponent(props.name)}`),
      request("/api/v1/groups"),
    ]);
    item.value = detail.container;
    groups.value = groupData.groups || [];
    check.value = detail.container.check || null;
    if (check.value) {
      checkUrl.value = check.value.url || "";
      checkInterval.value = check.value.interval || 60;
      checkEnabled.value = Boolean(check.value.enabled);
    }
    await loadBackups();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    loading.value = false;
  }
}

async function loadBackups() {
  try {
    const data = await listBackups(props.name);
    backups.value = data.backups || [];
  } catch {
    backups.value = [];
  }
}

async function act(action) {
  busy.value = true;
  try {
    await containerAction(item.value.id, action);
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}

async function update() {
  if (!window.confirm(`Обновить ${props.name}?`)) return;
  busy.value = true;
  try {
    const body = await updateContainer(item.value.id);
    message.value = body.changed ? `Обновлён ${body.old_image} → ${body.new_image}` : "Уже последняя версия";
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    busy.value = false;
  }
}

async function createBackup() {
  backupBusy.value = true;
  try {
    const body = await createBackupRequest(props.name);
    message.value = `Копия ${body.name} создана (${formatSize(body.size)}, файлов ${body.files})`;
    await loadBackups();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    backupBusy.value = false;
  }
}

async function restoreBackup(backup) {
  const confirm = window.prompt(`Введите имя сервиса «${props.name}», чтобы восстановить ${backup.name}`);
  if (confirm !== props.name) return;
  try {
    const body = await restoreBackupRequest(props.name, backup.name, confirm);
    message.value = `Восстановлено из ${body.restored}, safety-копия ${body.safety}`;
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function deleteBackup(backup) {
  if (!window.confirm(`Удалить копию ${backup.name}?`)) return;
  try {
    await deleteBackupRequest(props.name, backup.name);
    await loadBackups();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function editLink() {
  const value = window.prompt("Ссылка на сервис (пусто — автоматическая)", item.value.link_custom ? item.value.link : "");
  if (value === null) return;
  try {
    await setLink(props.name, value.trim());
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function assign(value) {
  try {
    await setGroup(props.name, value);
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function remove() {
  if (!window.confirm(`Удалить ${props.name}? Тома сохранятся.`)) return;
  try {
    await deleteContainer(item.value.id, true);
    router.push("/");
  } catch (err) {
    error.value = String(err.message || err);
  }
}

async function saveCheck() {
  checkSaving.value = true;
  try {
    const body = await saveCheckRequest(props.name, {
      url: checkUrl.value.trim(),
      interval: Number(checkInterval.value) || 60,
      enabled: checkEnabled.value,
    });
    check.value = body.check || null;
    message.value = check.value ? "Проверка сохранена" : "Проверка отключена";
    await load();
  } catch (err) {
    error.value = String(err.message || err);
  } finally {
    checkSaving.value = false;
  }
}

async function loadLogs() {
  logsBusy.value = true;
  try {
    const data = await loadLogsRequest(props.name);
    logsText.value = data.logs || "лог пуст";
  } catch (err) {
    logsText.value = String(err.message || err);
  } finally {
    logsBusy.value = false;
  }
}

function switchTab(name) {
  tab.value = name;
  router.replace({ query: { ...route.query, tab: name } });
  if (name === "logs") loadLogs();
}

watch(() => props.name, load);
onMounted(load);
</script>

<template>
  <div>
    <RouterLink to="/" class="muted">← Назад к обзору</RouterLink>

    <div v-if="loading" class="state">Загрузка…</div>
    <div v-else-if="error && !item" class="state error">
      <strong>Не удалось открыть сервис</strong>
      <p>{{ error }}</p>
    </div>

    <div v-else-if="item">
      <header class="page-head" style="margin-top: 14px">
        <div>
          <h1>{{ item.name }}</h1>
          <p class="sub">
            {{ item.image }} · {{ item.group ? item.group.name : "Без группы" }}
          </p>
        </div>
        <div class="head-actions">
          <a v-if="item.link" class="ghost" :href="item.link" target="_blank" rel="noopener noreferrer">
            Открыть ↗
          </a>
          <template v-if="can('control')">
            <button v-if="item.state === 'running'" class="ghost" :disabled="busy" @click="act('stop')">Стоп</button>
            <button v-else class="ghost" :disabled="busy" @click="act('start')">Запуск</button>
            <button v-if="item.state === 'running'" class="ghost" :disabled="busy" @click="act('restart')">Перезапуск</button>
          </template>
          <button v-if="can('manage')" class="primary" :disabled="busy" @click="update">Обновить</button>
        </div>
      </header>

      <div v-if="message" class="banner ok">{{ message }}</div>
      <div v-if="error" class="banner">{{ error }}</div>

      <div class="tabs">
        <button :class="{ active: tab === 'overview' }" @click="switchTab('overview')">Обзор</button>
        <button :class="{ active: tab === 'check' }" @click="switchTab('check')">Проверка</button>
        <button :class="{ active: tab === 'backups' }" @click="switchTab('backups')">Бэкапы</button>
        <button :class="{ active: tab === 'settings' }" @click="switchTab('settings')">Настройки</button>
        <button :class="{ active: tab === 'logs' }" @click="switchTab('logs')">Логи</button>
      </div>

      <section v-if="tab === 'overview'">
        <table class="props">
          <tbody>
            <tr><td>Состояние</td><td>{{ item.label }} ({{ item.status }})</td></tr>
            <tr><td>Образ</td><td>{{ item.image }}</td></tr>
            <tr><td>Порты</td><td>{{ portsText(item) || "нет" }}</td></tr>
            <tr><td>Сеть</td><td>{{ item.network || "—" }}</td></tr>
            <tr><td>Тома</td><td>
              <div v-if="item.volumes && item.volumes.length">
                <div v-for="volume in item.volumes" :key="volume.destination">
                  {{ volume.source }} → {{ volume.destination }}<span v-if="volume.readonly"> (ro)</span>
                </div>
              </div>
              <span v-else>нет</span>
            </td></tr>
            <tr><td>Группа</td><td>
              <select :value="item.group ? String(item.group.id) : ''" :disabled="!can('manage')" @change="assign($event.target.value)">
                <option value="">Без группы</option>
                <option v-for="group in groups" :key="group.id" :value="String(group.id)">{{ group.name }}</option>
              </select>
            </td></tr>
            <tr><td>Ссылка</td><td>
              <span v-if="item.link">{{ item.link }}</span>
              <button v-if="can('manage')" class="mini" @click="editLink">изменить</button>
            </td></tr>
            <tr><td>Идентификатор</td><td>#{{ item.short_id }}</td></tr>
          </tbody>
        </table>
      </section>

      <section v-else-if="tab === 'check'">
        <div class="form-grid">
          <label class="field">
            <span>Адрес проверки</span>
            <input v-model="checkUrl" placeholder="http://example.com:3001/" />
          </label>
          <label class="field">
            <span>Интервал, секунды</span>
            <input v-model="checkInterval" type="number" min="10" max="3600" />
          </label>
          <label class="field">
            <span>Включена</span>
            <select v-model="checkEnabled">
              <option :value="true">да</option>
              <option :value="false">нет</option>
            </select>
          </label>
        </div>

        <div v-if="check" class="props" style="margin-top: 14px">
          <div>
            Последняя проверка:
            {{ check.last_at ? new Date(check.last_at * 1000).toLocaleString("ru-RU") : "ещё не было" }}
          </div>
          <div>
            Результат: {{ check.last_ok ? "работает" : "ошибка" }}
            <span v-if="check.last_code"> · код {{ check.last_code }}</span>
          </div>
          <div v-if="check.last_error" class="muted">{{ check.last_error }}</div>
        </div>

        <div class="form-actions">
          <button v-if="can('manage')" class="primary" :disabled="checkSaving" @click="saveCheck">
            {{ checkSaving ? "Сохраняю…" : "Сохранить" }}
          </button>
        </div>
      </section>

      <section v-else-if="tab === 'backups'">
        <div class="head-actions" style="margin-bottom: 12px">
          <button v-if="can('manage')" class="primary" :disabled="backupBusy" @click="createBackup">
            {{ backupBusy ? "Создаю…" : "Создать копию" }}
          </button>
        </div>
        <ul v-if="backups.length" class="list">
          <li v-for="backup in backups" :key="backup.name">
            <div class="left">
              <span>{{ backup.name }}</span>
              <small>{{ new Date(backup.created * 1000).toLocaleString("ru-RU") }} · {{ formatSize(backup.size) }}</small>
            </div>
            <div class="head-actions">
              <template v-if="can('manage')">
                <button class="mini" @click="restoreBackup(backup)">Восстановить</button>
                <button class="mini danger" @click="deleteBackup(backup)">Удалить</button>
              </template>
            </div>
          </li>
        </ul>
        <p v-else class="muted">Копий пока нет</p>
      </section>

      <section v-else-if="tab === 'settings'">
        <table class="props">
          <tbody>
            <tr><td>Группа</td><td>
              <select :value="item.group ? String(item.group.id) : ''" :disabled="!can('manage')" @change="assign($event.target.value)">
                <option value="">Без группы</option>
                <option v-for="group in groups" :key="group.id" :value="String(group.id)">{{ group.name }}</option>
              </select>
            </td></tr>
            <tr><td>Ссылка</td><td>{{ item.link || "нет" }} <button class="mini" @click="editLink">изменить</button></td></tr>
            <tr><td>Удаление</td><td>
              <button v-if="can('manage')" class="mini danger" @click="remove">Удалить сервис</button>
              <span class="muted"> тома сохранятся</span>
            </td></tr>
          </tbody>
        </table>
      </section>
      <section v-else-if="tab === 'logs'">
        <div class="head-actions" style="margin-bottom: 10px">
          <button class="ghost" :disabled="logsBusy" @click="loadLogs">
            {{ logsBusy ? "Загружаю…" : "Обновить" }}
          </button>
        </div>
        <pre class="logs">{{ logsText || "Нажмите «Обновить», чтобы загрузить лог" }}</pre>
      </section>
    </div>
  </div>
</template>
