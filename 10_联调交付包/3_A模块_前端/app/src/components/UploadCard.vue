<script setup>
import { ref } from 'vue'

const emit = defineEmits(['pick', 'recognize'])
const props = defineProps({ busy: Boolean })
const input = ref(null)

function onFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    alert('只支持 JPG / PNG / WebP 截图')
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('图片不能超过 10MB')
    return
  }
  emit('recognize', file)
}
</script>

<template>
  <section class="card upload">
    <img class="hamster idle" src="../assets/hamster_05_xiumian.webp" alt="休眠的仓鼠" />
    <p class="hint">上传学习截图，我来打卡</p>
    <button class="primary" :disabled="busy" @click="input?.click()">
      {{ busy ? '识别中…' : '选一张截图' }}
    </button>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onFile" />
    <p class="tip">JPG / PNG / WebP，10MB 以内</p>
  </section>
</template>
