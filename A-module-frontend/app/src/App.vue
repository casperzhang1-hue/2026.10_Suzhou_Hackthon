<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import UploadCard from './components/UploadCard.vue'
import ConfirmCard from './components/ConfirmCard.vue'
import FallbackChips from './components/FallbackChips.vue'
import TodayScreen from './components/TodayScreen.vue'
import { recognize, submitRecord, fetchToday, API_BASE } from './api'
import { isNotStudyResult } from './warnings'
import { SCENARIOS } from './mockData'
import { recognitionToPetInput } from './bridge' // C 的 Recognition → 宠物参数桥

// 流程：upload → recognizing → confirm | fallback → done
const step = ref('upload')
const recognition = ref(null)
const lastLevel = ref(null)
const lastPetInput = ref(null)
const scenario = ref('normal')

// 今日状态：来自 B 的 GET /api/today（缺口行、宠物形态、活力值都由它给）
const today = ref(null)

async function loadToday() {
  today.value = await fetchToday()
}

// 进页面就拉一次；后端没起时 fetchToday 内部会回落并打 offline 标记，不会抛错
onMounted(loadToday)

// 等待态分段文案：C 实测平均 5.6s、最慢 11s、超时窗口 20s（无重试）
// 不做硬超时（C 承诺永远 resolve），只用文案管理心理预期
const waitMsg = ref('正在看你的截图…')
let waitTimers = []
function startWaitHint() {
  stopWaitHint()
  waitMsg.value = '正在看你的截图…'
  waitTimers = [
    setTimeout(() => (waitMsg.value = '这张图信息有点多，我还在看…'), 8000),
    setTimeout(() => (waitMsg.value = '马上就好，再等我一下…'), 15000),
    setTimeout(() => (waitMsg.value = '网络有点慢，我还在努力识别…'), 22000)
  ]
}
function stopWaitHint() {
  waitTimers.forEach(clearTimeout)
  waitTimers = []
}
onUnmounted(stopWaitHint)

async function onRecognize(file) {
  step.value = 'recognizing'
  startWaitHint()
  try {
    const data = await recognize(file, scenario.value)
    recognition.value = data
    lastLevel.value = data.encouragement?.level || null
    // 非学习图走兜底手填；其余（含 CORRECT_COUNT_INVALID）照常出确认卡，只拦提交
    step.value = isNotStudyResult(data) ? 'fallback' : 'confirm'
  } catch (e) {
    stopWaitHint()
    alert('识别失败：' + e.message)
    step.value = 'upload'
  } finally {
    stopWaitHint()
  }
}

async function onSubmit(payload) {
  await submitRecord(payload)
  lastLevel.value = recognition.value?.encouragement?.level || 'normal'
  lastPetInput.value = recognition.value ? recognitionToPetInput(recognition.value) : null
  step.value = 'done'
  await loadToday() // 入库后立刻刷新，让缺口行反映这次记录
}

function onManualSubmit(payload) {
  submitRecord(payload)
  lastLevel.value = 'normal'
  step.value = 'done'
  loadToday()
}

function reset() {
  step.value = 'upload'
  recognition.value = null
}
</script>

<template>
  <main class="page">
    <h1>考公陪跑 · 仓鼠打卡</h1>

    <!-- dev 演示工具栏：模拟 C 的 6 种返回，联调后整块删除 -->
    <div v-if="step === 'upload'" class="dev-bar">
      演示场景：
      <select v-model="scenario">
        <option v-for="s in SCENARIOS" :key="s.key" :value="s.key">{{ s.label }}</option>
      </select>
      <!-- 后端连通状态：现场排查跨域 / 端口最省时间的一行 -->
      <span class="api-status" :class="today && !today.offline ? 'on' : 'off'">
        后端 {{ today && today.base ? today.base : API_BASE }}
        <b>{{ today ? (today.offline ? '未连通' : '已连通') : '检测中' }}</b>
      </span>
    </div>

    <UploadCard v-if="step === 'upload'" @recognize="onRecognize" />

    <section v-else-if="step === 'recognizing'" class="card recognizing">
      <img class="hamster waiting" src="./assets/hamster_02_tashi.webp" alt="识别中" />
      <p>{{ waitMsg }}</p>
    </section>

    <ConfirmCard v-else-if="step === 'confirm'" :recognition="recognition" @submit="onSubmit" @cancel="reset" />
    <FallbackChips v-else-if="step === 'fallback'" @submit="onManualSubmit" @cancel="reset" />
    <TodayScreen v-else-if="step === 'done'" :level="lastLevel" :pet-input="lastPetInput" :today="today" @again="reset" />
  </main>
</template>

<style scoped>
.api-status {
  margin-left: 10px;
  font-size: 11.5px;
  color: #8a8578;
}
.api-status b {
  margin-left: 4px;
}
.api-status.on b {
  color: #2e7d52;
}
.api-status.off b {
  color: #c0392b;
}
</style>

