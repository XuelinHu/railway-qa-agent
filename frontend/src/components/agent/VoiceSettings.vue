<script setup lang="ts">
/** Voice preferences. Shared state, so changes apply to the open panel too. */
import { computed } from 'vue'

import { useSpeech } from '@/composables/useSpeech'

const speech = useSpeech()

const modeLabel = computed(() =>
  speech.asrMode.value === 'browser'
    ? '浏览器识别（无需联网）'
    : speech.asrMode.value === 'server'
      ? '服务端识别（浏览器不支持时兜底）'
      : '不可用',
)

const speakModeLabel = computed(() =>
  speech.ttsMode.value === 'browser'
    ? '浏览器合成'
    : speech.ttsMode.value === 'server'
      ? '服务端合成'
      : '不可用',
)

const voices = computed(() => speech.capabilities.value?.voices ?? [])
</script>

<template>
  <div class="voice-settings">
    <el-form label-width="96px" label-position="left">
      <el-form-item label="语音播报">
        <el-switch
          :model-value="speech.autoSpeak.value"
          @update:model-value="speech.setAutoSpeak($event as boolean)"
        />
        <span class="voice-settings__note">回答完成后自动朗读</span>
      </el-form-item>

      <el-form-item label="连续对话">
        <el-switch
          :model-value="speech.continuous.value"
          @update:model-value="speech.setContinuous($event as boolean)"
        />
        <span class="voice-settings__note">播报结束后自动重新聆听，无需点击</span>
      </el-form-item>

      <el-form-item label="语速">
        <el-slider
          :model-value="speech.rate.value"
          :min="-50"
          :max="100"
          :step="10"
          show-stops
          @update:model-value="speech.setRate($event as number)"
        />
      </el-form-item>

      <el-form-item v-if="voices.length" label="音色">
        <el-select
          :model-value="speech.voiceName.value"
          placeholder="默认音色"
          clearable
          class="voice-settings__select"
          @update:model-value="speech.setVoice($event as string | null)"
        >
          <el-option
            v-for="voice in voices"
            :key="voice.name"
            :label="`${voice.label}（${voice.language}）`"
            :value="voice.name"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <el-alert type="info" :closable="false" show-icon>
      <p>识别方式：{{ modeLabel }}</p>
      <p>合成方式：{{ speakModeLabel }}</p>
      <p v-if="speech.microphoneHint.value" class="voice-settings__warn">
        {{ speech.microphoneHint.value }}
      </p>
    </el-alert>

    <p class="voice-settings__tip">
      播报过程中点击麦克风可立即打断；点按麦克风再次静音即结束聆听。
    </p>
  </div>
</template>

<style scoped>
.voice-settings {
  display: grid;
  gap: 14px;
  max-width: 460px;
}

.voice-settings__note {
  margin-left: 12px;
  color: #5c6972;
  font-size: 12px;
}

.voice-settings__select {
  width: 100%;
}

.voice-settings__warn {
  color: #b45309;
}

.voice-settings :deep(.el-alert__content p) {
  margin: 2px 0;
  font-size: 12px;
}

.voice-settings__tip {
  margin-bottom: 0;
  color: #5c6972;
  font-size: 12px;
}
</style>
