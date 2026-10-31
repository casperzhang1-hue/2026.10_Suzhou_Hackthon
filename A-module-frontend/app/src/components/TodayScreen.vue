<script setup>
import { computed } from 'vue'
import { getPhrase } from '../phrases'
import { LEVEL_TO_STATE } from '../bridge'

// today = /api/today 的返回（后端算好的今日状态 + 缺口行）
const props = defineProps({ level: String, petInput: Object, today: Object })

// 静态收集全部五态图（动态字符串路径 Vite 打包解析不到）
const IMAGES = import.meta.glob('../assets/hamster_*.webp', { eager: true, import: 'default' })

// 后端 pet_state 枚举（engine.js）→ 素材文件名
// 同时兼容中文枚举，万一 B 返回「疲惫」这类中文也不会掉进默认休眠态
const PET_STATE_FILE = {
  vigour: '01_yuanqi', steady: '02_tashi', tired: '03_pibei',
  wilt: '04_nianle', sleep: '05_xiumian',
  元气: '01_yuanqi', 踏实: '02_tashi', 疲惫: '03_pibei',
  蔫了: '04_nianle', 休眠: '05_xiumian',
}

// 形态优先级：后端算的 pet_state > 本地按 level 直映 > 休眠（今日无记录）
const stateFile = computed(() => {
  const fromApi = props.today?.pet_state && PET_STATE_FILE[props.today.pet_state]
  if (fromApi) return fromApi
  const byLevel = LEVEL_TO_STATE[props.level]
  return (byLevel && PET_STATE_FILE[byLevel]) || '05_xiumian'
})
const stateSrc = computed(() => IMAGES[`../assets/hamster_${stateFile.value}.webp`])

// 话术档位：后端 phrase_level 优先（后端已按 pet_state 映射过），其次用识别的 level
const phrase = computed(() => getPhrase(props.today?.phrase_level || props.level || 'normal'))

// 缺口行 —— 只读后端数据，不按话术档位猜（RK-08 唯一防法）
// 没拉到就显示「—」，绝不编一个「欠 2 次」
const gap = computed(() => {
  const g = props.today?.gap
  if (!g || typeof g.week_target !== 'number') return '本周缺口 —'
  return g.owed > 0
    ? `本周 ${g.week_done}/${g.week_target}，还欠 ${g.owed} 次`
    : `本周全勤 ${g.week_done}/${g.week_target}，明天继续`
})

// 断网 / 后端未起：显式标记，不冒充实时数据
const offline = computed(() => !!props.today?.offline)
const offlineText = computed(() => (props.today?.mock ? '离线 · 演示数据' : '离线 · 上次同步'))
</script>

<template>
  <section class="card today">
    <div class="stage">
      <img class="hamster" :src="stateSrc" alt="仓鼠" />
      <div class="bubble">{{ phrase }}</div>
    </div>

    <p class="gap">
      {{ gap }}
      <span v-if="offline" class="offline-tag">{{ offlineText }}</span>
    </p>

    <p v-if="today && today.user_state" class="state-line">
      今天你：<b>{{ today.user_state }}</b><span v-if="today.vitality != null"> · 活力 {{ today.vitality }}</span>
    </p>

    <button class="ghost" @click="$emit('again')">再记一次</button>
  </section>
</template>

<style scoped>
.state-line {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--ink2, #8a8578);
}
.state-line b {
  color: var(--ink, #3a3630);
  font-weight: 600;
}
.offline-tag {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
  color: #8a8578;
  background: rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0, 0, 0, 0.08);
}
</style>
