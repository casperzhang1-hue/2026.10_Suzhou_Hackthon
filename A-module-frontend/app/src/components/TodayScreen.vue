<script setup>
import { computed } from 'vue'
import { getPhrase } from '../phrases'
import { recognitionToPetInput, LEVEL_TO_STATE } from '../bridge'

const props = defineProps({ level: String, petInput: Object })

// 静态收集全部五态图（动态字符串路径 Vite 打包解析不到）
const IMAGES = import.meta.glob('../assets/hamster_*.webp', { eager: true, import: 'default' })

// 优先走 petInput 算法映射；没有的话按 level 直映；今日无记录是休眠态
const STATE_BY_LEVEL = { excellent: '01_yuanqi', good: '02_tashi', normal: '03_pibei', low: '04_nianle' }
const stateFile = computed(() => STATE_BY_LEVEL[props.level] || '05_xiumian')
const stateSrc = computed(() => IMAGES[`../assets/hamster_${stateFile.value}.webp`])
const phrase = computed(() => getPhrase(props.level || 'normal'))
const gap = computed(() => (props.level === 'low' ? '本周欠 2 次' : '本周全勤，明天继续'))
</script>

<template>
  <section class="card today">
    <div class="stage">
      <img class="hamster" :src="stateSrc" alt="仓鼠" />
      <div class="bubble">{{ phrase }}</div>
    </div>
    <p class="gap">{{ gap }}</p>
    <button class="ghost" @click="$emit('again')">再记一次</button>
  </section>
</template>
