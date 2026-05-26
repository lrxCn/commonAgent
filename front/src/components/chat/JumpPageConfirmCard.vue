<script setup lang="ts">
import { NButton, NSpace, NText } from "naive-ui";
import { computed } from "vue";

import type { JumpPagePromptStatus } from "@/types";

const props = defineProps<{
  pageLabel: string;
  status: JumpPagePromptStatus;
  statusDetail?: string;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

const statusText = computed(() => {
  switch (props.status) {
    case "confirmed":
      return "已跳转";
    case "cancelled":
      return "已取消跳转";
    case "invalid":
      return props.statusDetail ?? "无法跳转";
    case "historical":
      return "历史跳转建议（请重新发起对话以执行）";
    default:
      return null;
  }
});

const showActions = computed(() => props.status === "pending");
</script>

<template>
  <div class="jump-page-card" :class="`jump-page-card--${status}`">
    <p class="jump-page-card__title">页面跳转</p>
    <p v-if="status === 'invalid'" class="jump-page-card__body">
      无法跳转到
      <strong>{{ pageLabel }}</strong>
      。
    </p>
    <p v-else class="jump-page-card__body">
      是否前往
      <strong>{{ pageLabel }}</strong>
      ？
    </p>
    <p v-if="statusText" class="jump-page-card__status">
      {{ statusText }}
    </p>
    <n-space v-if="showActions" :size="8" class="jump-page-card__actions">
      <n-button type="primary" size="small" @click="emit('confirm')">
        确认跳转
      </n-button>
      <n-button size="small" @click="emit('cancel')">
        取消
      </n-button>
    </n-space>
    <n-text v-else-if="status === 'historical'" depth="3" class="jump-page-card__hint">
      该建议来自历史记录，无法再次确认。
    </n-text>
  </div>
</template>

<style scoped>
.jump-page-card {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.jump-page-card--confirmed {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.jump-page-card--cancelled,
.jump-page-card--historical {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.jump-page-card--invalid {
  border-color: #fecaca;
  background: #fef2f2;
}

.jump-page-card__title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
}

.jump-page-card--confirmed .jump-page-card__title {
  color: #15803d;
}

.jump-page-card--invalid .jump-page-card__title {
  color: #b91c1c;
}

.jump-page-card__body {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #1e3a5f;
}

.jump-page-card__status {
  margin: 8px 0 0;
  font-size: 13px;
  color: #4b5563;
}

.jump-page-card__actions {
  margin-top: 10px;
}

.jump-page-card__hint {
  display: block;
  margin-top: 6px;
  font-size: 12px;
}
</style>
