<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

import { can } from "../api";
import { containerAction, createBackup, deleteContainer, setLink, updateContainer } from "../containers";
import { portsText } from "../format";

const props = defineProps({ item: { type: Object, required: true } });
const emit = defineEmits(["refresh"]);

const router = useRouter();
const busy = ref(false);

function open() {
  router.push(`/services/${encodeURIComponent(props.item.name)}`);
}

async function act(action) {
  busy.value = true;
  try {
    await containerAction(props.item.id, action);
    emit("refresh");
  } catch (err) {
    window.alert(String(err.message || err));
  } finally {
    busy.value = false;
  }
}

async function update() {
  if (!window.confirm(`Обновить ${props.item.name}?`)) return;
  busy.value = true;
  try {
    const body = await updateContainer(props.item.id);
    window.alert(body.changed ? `Обновлён ${body.old_image} → ${body.new_image}` : "Уже последняя версия");
    emit("refresh");
  } catch (err) {
    window.alert(String(err.message || err));
  } finally {
    busy.value = false;
  }
}

async function backup() {
  busy.value = true;
  try {
    const body = await createBackup(props.item.name);
    window.alert(`Копия ${body.name} создана (${body.size} байт)`);
  } catch (err) {
    window.alert(String(err.message || err));
  } finally {
    busy.value = false;
  }
}

async function editLink() {
  const value = window.prompt("Ссылка на сервис (пусто — автоматическая)", props.item.link_custom ? props.item.link : "");
  if (value === null) return;
  try {
    await setLink(props.item.name, value.trim());
    emit("refresh");
  } catch (err) {
    window.alert(String(err.message || err));
  }
}

async function remove() {
  if (!window.confirm(`Удалить ${props.item.name}? Тома сохранятся.`)) return;
  busy.value = true;
  try {
    await deleteContainer(props.item.id, true);
    emit("refresh");
  } catch (err) {
    window.alert(String(err.message || err));
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <article class="card" @click="open">
    <div class="row">
      <span class="dot" :class="item.state" />
      <h3>{{ item.name }}</h3>
      <span class="state-label">{{ item.label }}</span>
    </div>

    <p class="image">{{ item.image }}</p>
    <p class="ports">{{ portsText(item) }}</p>
    <p class="ident">#{{ item.short_id }} · {{ item.group ? item.group.name : "Без группы" }}</p>
    <p v-if="item.check" class="ident">
      проверка: {{ item.check.last_ok ? "ок" : "ошибка" }}
      <span v-if="item.check.last_code"> · {{ item.check.last_code }}</span>
    </p>

    <div class="card-actions">
      <a
        v-if="item.link"
        class="open"
        :href="item.link"
        target="_blank"
        rel="noopener noreferrer"
        @click.stop
      >Открыть ↗</a>
      <span v-else class="open muted">ссылки нет</span>

      <details class="menu" @click.stop>
        <summary>⋯</summary>
        <div class="menu-list">
          <template v-if="can('control')">
            <button v-if="item.state === 'running'" :disabled="busy" @click="act('stop')">Стоп</button>
            <button v-else :disabled="busy" @click="act('start')">Запуск</button>
            <button v-if="item.state === 'running'" :disabled="busy" @click="act('restart')">Перезапуск</button>
          </template>
          <template v-if="can('manage')">
            <button :disabled="busy" @click="update">Обновить</button>
            <button :disabled="busy" @click="backup">Бэкап</button>
            <button @click="editLink">Ссылка</button>
            <button class="danger" @click="remove">Удалить</button>
          </template>
          <button @click="open">Подробнее</button>
        </div>
      </details>
    </div>
  </article>
</template>
