<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NText,
} from "naive-ui";

import { formatCreateStudentPrefill } from "@/client-actions/create-student";
import type { CreateStudentFormStatus, Student, StudentCreateRequest } from "@/types";

const props = defineProps<{
  prefill: Partial<StudentCreateRequest>;
  status: CreateStudentFormStatus;
  errorDetail?: string;
  fieldErrors?: Record<string, string>;
  createdStudent?: Student;
}>();

const emit = defineEmits<{
  submit: [payload: StudentCreateRequest];
  cancel: [];
}>();

const statusOptions = [
  { label: "在读", value: "active" },
  { label: "休学", value: "inactive" },
];

const studentNo = ref("");
const name = ref("");
const className = ref("");
const status = ref("active");

function applyPrefill(prefill: Partial<StudentCreateRequest>): void {
  studentNo.value = prefill.student_no ?? "";
  name.value = prefill.name ?? "";
  className.value = prefill.class_name ?? "";
  status.value = prefill.status ?? "active";
}

watch(
  () => props.prefill,
  (prefill) => {
    if (props.status === "editable") {
      applyPrefill(prefill);
    }
  },
  { deep: true },
);

applyPrefill(props.prefill);

const isReadonly = computed(
  () =>
    props.status === "submitting" ||
    props.status === "success" ||
    props.status === "cancelled" ||
    props.status === "historical",
);

const showActions = computed(() => props.status === "editable" || props.status === "error");

const statusText = computed(() => {
  switch (props.status) {
    case "success":
      if (props.createdStudent) {
        const s = props.createdStudent;
        return `已创建：${s.name}（${s.student_no}）`;
      }
      return "学生已创建";
    case "cancelled":
      return "已取消新建";
    case "historical": {
      const lines = formatCreateStudentPrefill(props.prefill);
      if (lines.length > 0) {
        return `历史新建建议（${lines.join("，")}）`;
      }
      return "历史新建建议（请重新发起对话以提交）";
    }
    case "error":
      return props.errorDetail ?? "创建失败，请修改后重试";
    default:
      return null;
  }
});

const cardClass = computed(() => `create-student-card--${props.status}`);

function onSubmit(): void {
  const payload: StudentCreateRequest = {
    student_no: studentNo.value.trim(),
    name: name.value.trim(),
    class_name: className.value.trim() || null,
    status: status.value,
  };
  emit("submit", payload);
}
</script>

<template>
  <div class="create-student-card" :class="cardClass">
    <p class="create-student-card__title">新建学生</p>

    <p v-if="statusText" class="create-student-card__status">
      {{ statusText }}
    </p>

    <n-form
      v-if="status !== 'success'"
      label-placement="top"
      size="small"
      class="create-student-card__form"
      @submit.prevent="onSubmit"
    >
      <n-form-item
        label="学号"
        required
        :feedback="fieldErrors?.student_no"
        :validation-status="fieldErrors?.student_no ? 'error' : undefined"
      >
        <n-input
          v-model:value="studentNo"
          placeholder="学号"
          :disabled="isReadonly"
        />
      </n-form-item>
      <n-form-item
        label="姓名"
        required
        :feedback="fieldErrors?.name"
        :validation-status="fieldErrors?.name ? 'error' : undefined"
      >
        <n-input
          v-model:value="name"
          placeholder="姓名"
          :disabled="isReadonly"
        />
      </n-form-item>
      <n-form-item
        label="班级"
        :feedback="fieldErrors?.class_name"
        :validation-status="fieldErrors?.class_name ? 'error' : undefined"
      >
        <n-input
          v-model:value="className"
          placeholder="班级（可选）"
          :disabled="isReadonly"
        />
      </n-form-item>
      <n-form-item
        label="状态"
        :feedback="fieldErrors?.status"
        :validation-status="fieldErrors?.status ? 'error' : undefined"
      >
        <n-select
          v-model:value="status"
          :options="statusOptions"
          :disabled="isReadonly"
        />
      </n-form-item>

      <n-space v-if="showActions" :size="8" class="create-student-card__actions">
        <n-button
          type="primary"
          size="small"
          attr-type="submit"
          :loading="status === 'submitting'"
          @click="onSubmit"
        >
          确定
        </n-button>
        <n-button size="small" :disabled="status === 'submitting'" @click="emit('cancel')">
          取消
        </n-button>
      </n-space>
      <n-text v-if="status === 'historical'" depth="3" class="create-student-card__hint">
        该建议来自历史记录，无法再次提交。
      </n-text>
    </n-form>
  </div>
</template>

<style scoped>
.create-student-card {
  margin-top: 8px;
  padding: 12px 13px;
  border-radius: 8px;
  border: 1px solid #d7e3f4;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}

.create-student-card--success {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.create-student-card--cancelled,
.create-student-card--historical {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.create-student-card--error {
  border-color: #fecaca;
  background: #fef2f2;
}

.create-student-card__title {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #1f4fbf;
}

.create-student-card--success .create-student-card__title {
  color: #15803d;
}

.create-student-card--error .create-student-card__title {
  color: #b91c1c;
}

.create-student-card__status {
  margin: 0 0 8px;
  font-size: 13px;
  color: #374151;
}

.create-student-card__form {
  margin-top: 4px;
}

.create-student-card__actions {
  margin-top: 4px;
}

.create-student-card__hint {
  display: block;
  margin-top: 6px;
  font-size: 12px;
}

.create-student-card :deep(.n-button--primary-type) {
  --n-color: #2563eb !important;
  --n-color-hover: #1d4ed8 !important;
  --n-color-pressed: #1e40af !important;
  --n-color-focus: #2563eb !important;
  --n-border: 1px solid #2563eb !important;
  --n-border-hover: 1px solid #1d4ed8 !important;
  --n-border-pressed: 1px solid #1e40af !important;
  --n-border-focus: 1px solid #2563eb !important;
  --n-border-radius: 7px !important;
}
</style>
