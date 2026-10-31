<script setup>
import { computed, reactive, ref } from 'vue'
import { getWarnings, hasBlockWarning } from '../warnings'
import { MODULE_NAMES, APP_NAMES } from '../mockData'

const props = defineProps({ recognition: Object })
const emit = defineEmits(['submit', 'cancel'])

const warnings = computed(() => getWarnings(props.recognition).filter((w) => w.level === 'hint'))
const blockWarnings = computed(() => getWarnings(props.recognition).filter((w) => w.level === 'block'))

const form = reactive({
  source_app: props.recognition.source_app || '',
  event_date: props.recognition.event_date || '',
  event_time: props.recognition.event_time || '',
  duration_minutes: props.recognition.duration_minutes ?? '',
  modules: (props.recognition.modules.length
    ? props.recognition.modules
    : [{ name: MODULE_NAMES[0], question_count: '', correct_count: '' }]
  ).map((m) => ({ ...m })),
})
const edited = reactive(new Set())

function touch(key) {
  edited.add(key)
}

function addModule() {
  form.modules.push({ name: MODULE_NAMES[0], question_count: '', correct_count: '' })
}
function removeModule(i) {
  form.modules.splice(i, 1)
  touch('modules')
}

const rowInvalid = (m) => m.correct_count !== '' && Number(m.correct_count) > Number(m.question_count)
const anyRowInvalid = computed(() => form.modules.some(rowInvalid))
const totalQuestions = computed(() =>
  form.modules.reduce((s, m) => s + (Number(m.question_count) || 0), 0)
)

const duplicate = computed(() => blockWarnings.value.some((w) => w.code === 'DUPLICATE_RECORD'))
const canSubmit = computed(() => !anyRowInvalid.value && !duplicate.value && form.source_app !== '')

function onSubmit() {
  if (!canSubmit.value) return
  emit('submit', {
    record: {
      source_app: form.source_app,
      event_date: form.event_date || null,
      event_time: form.event_time || null,
      duration_minutes: form.duration_minutes === '' ? null : Math.round(Number(form.duration_minutes)),
      modules: form.modules.map((m) => ({
        name: m.name,
        question_count: Number(m.question_count) || 0,
        correct_count: m.correct_count === '' ? null : Number(m.correct_count),
      })),
      total_questions: totalQuestions.value,
      accuracy: null, // 服务端算，或按 Q4：部分缺用有数据的模块算
    },
    recognition_ref: props.recognition.recognition,
    edited_fields: [...edited],
    confirmed_at: new Date().toISOString(),
  })
}
</script>

<template>
  <section class="card confirm">
    <div v-for="w in warnings" :key="w.code" class="banner warn">{{ w.text }}</div>
    <div v-for="w in blockWarnings" :key="w.code" class="banner block" :class="{ dup: duplicate }">
      {{ w.text }}
    </div>

    <h3>确认一下再记</h3>

    <template v-if="!duplicate">
      <label>来源
        <select v-if="!recognition.source_app" v-model="form.source_app" @change="touch('source_app')">
          <option value="" disabled>选一个 App</option>
          <option v-for="a in APP_NAMES" :key="a">{{ a }}</option>
        </select>
        <input v-else v-model="form.source_app" @input="touch('source_app')" />
      </label>
      <label>学习日期 <input type="date" v-model="form.event_date" @input="touch('event_date')" /></label>
      <label>学习时间 <input type="time" v-model="form.event_time" @input="touch('event_time')" /></label>
      <label>时长（分钟） <input type="number" min="0" step="1" v-model="form.duration_minutes" @input="touch('duration_minutes')" /></label>

      <div class="modules">
        <div v-for="(m, i) in form.modules" :key="i" class="module-row" :class="{ bad: rowInvalid(m) }">
          <select v-model="m.name" @change="touch('modules')">
            <option v-for="n in MODULE_NAMES" :key="n">{{ n }}</option>
          </select>
          <input type="number" min="0" placeholder="题量" v-model="m.question_count" @input="touch('modules')" />
          <input type="number" min="0" placeholder="正确数" v-model="m.correct_count" @input="touch('modules')" />
          <button class="mini" @click="removeModule(i)">删</button>
        </div>
        <button class="mini add" @click="addModule">+ 加一个模块</button>
      </div>
      <p class="sum">共 {{ totalQuestions }} 题</p>
    </template>

    <div class="actions">
      <button class="ghost" @click="emit('cancel')">重传一张</button>
      <button class="primary" :disabled="!canSubmit" @click="onSubmit">
        {{ duplicate ? '知道了' : anyRowInvalid ? '改对才能提交' : '没问题' }}
      </button>
    </div>
  </section>
</template>
