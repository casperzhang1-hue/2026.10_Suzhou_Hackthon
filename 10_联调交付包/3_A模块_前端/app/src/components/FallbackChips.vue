<script setup>
import { ref } from 'vue'
import { MODULE_NAMES, APP_NAMES } from '../mockData'

const emit = defineEmits(['submit', 'cancel'])

const form = ref({ source_app: '', event_date: today(), duration_minutes: '', modules: [{ name: MODULE_NAMES[0], question_count: '', correct_count: '' }] })

function today() {
  return new Date().toISOString().slice(0, 10)
}
function onSubmit() {
  emit('submit', {
    record: {
      source_app: form.value.source_app,
      event_date: form.value.event_date,
      event_time: null,
      duration_minutes: form.value.duration_minutes === '' ? null : Math.round(Number(form.value.duration_minutes)),
      modules: form.value.modules.map((m) => ({
        name: m.name,
        question_count: Number(m.question_count) || 0,
        correct_count: m.correct_count === '' ? null : Number(m.correct_count),
      })),
      total_questions: form.value.modules.reduce((s, m) => s + (Number(m.question_count) || 0), 0),
      accuracy: null,
    },
    recognition_ref: null,
    edited_fields: ['source_app'],
    confirmed_at: new Date().toISOString(),
    manual: true,
  })
}
</script>

<template>
  <section class="card fallback">
    <img class="hamster sad" src="../assets/hamster_04_nianle.webp" alt="蔫了的仓鼠" />
    <h3>这张没认出来，手动记一下</h3>
    <label>来源
      <select v-model="form.source_app">
        <option value="" disabled>选一个 App</option>
        <option v-for="a in APP_NAMES" :key="a">{{ a }}</option>
      </select>
    </label>
    <label>学习日期 <input type="date" v-model="form.event_date" /></label>
    <label>时长（分钟） <input type="number" min="0" step="1" v-model="form.duration_minutes" /></label>
    <div class="modules">
      <div v-for="(m, i) in form.modules" :key="i" class="module-row">
        <select v-model="m.name">
          <option v-for="n in MODULE_NAMES" :key="n">{{ n }}</option>
        </select>
        <input type="number" min="0" placeholder="题量" v-model="m.question_count" />
        <input type="number" min="0" placeholder="正确数" v-model="m.correct_count" />
      </div>
    </div>
    <div class="actions">
      <button class="ghost" @click="emit('cancel')">重传一张</button>
      <button class="primary" :disabled="form.source_app === ''" @click="onSubmit">记好了</button>
    </div>
  </section>
</template>
