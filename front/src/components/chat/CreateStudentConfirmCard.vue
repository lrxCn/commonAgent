<script setup lang="ts">
import { NButton, NSpace, NText } from "naive-ui";
import { computed } from "vue";

import type { CreateStudentPromptStatus } from "@/types";

const props = defineProps<{
  prefillLines: string[];
  status: CreateStudentPromptStatus;
  statusDetail?: string;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

const statusText = computed(() => {
  switch (props.status) {
    case "confirmed":
      return "已打开新建学生表单";
    case "cancelled":
      return "已取消";
    case "invalid":
      return props.statusDetail ?? "无法打开表单";
    case "historical":
      return "历史新建建议（请重新发起对话以执行）";
    default:
      return null;
  }
});

const showActions = computed(() => props.status === "pending");
const hasPrefill = computed(() => props.prefillLines.length > 0);
</script>

<template>
  <div class="create-student-card" :class="`create-student-card--${status}`">
    <p class="create-student-card__title">新建学生</p>
    <p v-if="status === 'invalid'" class="create-student-card__body">
      {{ statusDetail ?? "无法打开新建学生表单。" }}
    </p>
    <template v-else>
      <p class="create-student-card__body">
        是否前往<strong>学生管理</strong>并打开新建学生表单？
      </p>
      <p v-if="hasPrefill" class="create-student-card__prefill-title">将预填以下字段：</p>
      <ul v-if="hasPrefill" class="create-student-card__prefill">
        <li v-for="line in prefillLines" :key="line">{{ line }}</li>
      </ul>
      <p v-else class="create-student-card__hint">未指定预填字段，表单将为空。</p>
      <p class="create-student-card__note">打开后仍需您点击「保存」才会提交。</p>
    </template>
    <p v-if="statusText" class="create-student-card__status">
      {{ statusText }}
    </p>
    <n-space v-if="showActions" :size="8" class="create-student-card__actions">
      <n-button type="primary" size="small" @click="emit('confirm')">
        确认打开
      </n-button>
      <n-button size="small" @click="emit('cancel')">
        取消
      </n-button>
    </n-space>
    <n-text v-else-if="status === 'historical'" depth="3" class="create-student-card__historical">
      该建议来自历史记录，无法再次确认。
    </n-text>
  </div>
</template>

<style scoped>
.create-student-card {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.create-student-card--confirmed {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.create-student-card--cancelled,
.create-student-card--historical {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.create-student-card--invalid {
  border-color: #fecaca;
  background: #fef2f2;
}

.create-student-card__title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
}

.create-student-card--confirmed .create-student-card__title {
  color: #15803d;
}

.create-student-card--invalid .create-student-card__title {
  color: #b91c1c;
}

.create-student-card__body {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #1e3a5f;
}

.create-student-card__prefill-title {
  margin: 8px 0 4px;
  font-size: 13px;
  color: #374151;
}

.create-student-card__prefill {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.5;
  color: #1e3a5f;
}

.create-student-card__hint,
.create-student-card__note {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.create-student-card__status {
  margin: 8px 0 0;
  font-size: 13px;
  color: #4b5563;
}

.create-student-card__actions {
  margin-top: 10px;
}

.create-student-card__historical {
  display: block;
  margin-top: 6px;
  font-size: 12px;
}
</style>
