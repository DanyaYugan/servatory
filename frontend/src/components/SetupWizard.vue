<script setup>
import ProfileForm from "./ProfileForm.vue";

defineProps({ initial: { type: Object, required: true } });
const emit = defineEmits(["done"]);
</script>

<template>
  <div class="wizard-backdrop">
    <section class="wizard-card">
      <h1>Первый запуск</h1>
      <p class="sub">
        Как называется панель и по какому адресу она будет открываться.
        Это можно изменить позже в настройках.
      </p>
      <ProfileForm
        :initial="initial"
        skip-label="Пропустить"
        @saved="emit('done')"
        @skip="emit('done')"
      />
    </section>
  </div>
</template>
