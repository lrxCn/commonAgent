<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import {
  NButton,
  NDataTable,
  NInput,
  NPagination,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
  type DataTableColumns,
} from "naive-ui";

import { formatListStudentsQuerySummary } from "@/client-actions/list-students";
import type { ListStudentsMessage, Student, StudentListParams, StudentListResponse } from "@/types";

const props = defineProps<{
  query: StudentListParams;
  status: ListStudentsMessage["status"];
  data?: StudentListResponse;
  errorDetail?: string;
}>();

const emit = defineEmits<{
  refresh: [query: StudentListParams];
}>();

const statusOptions = [
  { label: "在读", value: "active" },
  { label: "休学", value: "inactive" },
];

const statusLabelMap: Record<string, string> = {
  active: "在读",
  inactive: "休学",
};

const searchDraft = ref("");
const statusDraft = ref<string | null>(null);

const isReadonly = computed(() => props.status === "historical");

const pageSize = computed(() => props.query.limit ?? 10);

const currentPage = computed(() => {
  const offset = props.query.offset ?? 0;
  return Math.floor(offset / pageSize.value) + 1;
});

const tableRows = computed(() => props.data?.items ?? []);

const total = computed(() => props.data?.total ?? 0);

const showTable = computed(
  () =>
    props.status === "ready" ||
    props.status === "loading" ||
    (props.status === "historical" && tableRows.value.length > 0),
);

const columns = computed<DataTableColumns<Student>>(() => [
  { title: "学号", key: "student_no", width: 88, ellipsis: { tooltip: true } },
  { title: "姓名", key: "name", width: 72, ellipsis: { tooltip: true } },
  {
    title: "班级",
    key: "class_name",
    width: 88,
    ellipsis: { tooltip: true },
    render: (row) => row.class_name || "—",
  },
  {
    title: "状态",
    key: "status",
    width: 64,
    render: (row) =>
      h(
        NTag,
        {
          type: row.status === "active" ? "success" : "default",
          size: "small",
          round: true,
        },
        { default: () => statusLabelMap[row.status] ?? row.status },
      ),
  },
]);

const historicalSummary = computed(() => formatListStudentsQuerySummary(props.query));

const statusHint = computed(() => {
  if (props.status === "error") {
    return props.errorDetail ?? "加载学生列表失败";
  }
  if (props.status === "historical" && !showTable.value) {
    return `历史查询条件：${historicalSummary.value}`;
  }
  return null;
});

function syncDraftFromQuery(query: StudentListParams): void {
  searchDraft.value = query.search ?? "";
  statusDraft.value = query.status ?? null;
}

watch(
  () => props.query,
  (query) => {
    if (!isReadonly.value) {
      syncDraftFromQuery(query);
    }
  },
  { deep: true, immediate: true },
);

function buildQuery(overrides: Partial<StudentListParams>): StudentListParams {
  const next: StudentListParams = {
    offset: props.query.offset ?? 0,
    limit: pageSize.value,
  };
  if (props.query.class_name) {
    next.class_name = props.query.class_name;
  }
  const merged = { ...next, ...props.query, ...overrides };
  const search = merged.search?.trim();
  if (search) {
    merged.search = search;
  } else {
    delete merged.search;
  }
  if (!merged.status) {
    delete merged.status;
  }
  if (!merged.class_name) {
    delete merged.class_name;
  }
  return merged;
}

function onSearch(): void {
  emit(
    "refresh",
    buildQuery({
      offset: 0,
      search: searchDraft.value.trim() || undefined,
      status: statusDraft.value ?? undefined,
    }),
  );
}

function onPageChange(page: number): void {
  emit(
    "refresh",
    buildQuery({
      offset: (page - 1) * pageSize.value,
    }),
  );
}

function onPageSizeChange(size: number): void {
  emit(
    "refresh",
    buildQuery({
      offset: 0,
      limit: size,
    }),
  );
}
</script>

<template>
  <div class="student-list-card" :class="`student-list-card--${status}`">
    <p class="student-list-card__title">学生列表</p>

    <p v-if="statusHint" class="student-list-card__hint">
      {{ statusHint }}
    </p>

    <n-space v-if="!isReadonly" vertical :size="8" class="student-list-card__toolbar">
      <n-space wrap :size="8">
        <n-input
          v-model:value="searchDraft"
          placeholder="搜索姓名 / 学号 / 班级"
          clearable
          size="small"
          style="width: 100%; min-width: 160px; max-width: 220px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <n-select
          v-model:value="statusDraft"
          :options="statusOptions"
          placeholder="状态"
          clearable
          size="small"
          style="width: 100px"
        />
        <n-button size="small" type="primary" :disabled="status === 'loading'" @click="onSearch">
          查询
        </n-button>
      </n-space>
    </n-space>

    <n-spin v-if="showTable" :show="status === 'loading'" class="student-list-card__table-wrap">
      <n-data-table
        size="small"
        :columns="columns"
        :data="tableRows"
        :bordered="false"
        :single-line="false"
        :row-key="(row: Student) => row.student_id"
        :scroll-x="320"
      />
      <n-pagination
        v-if="!isReadonly && status !== 'error'"
        class="student-list-card__pagination"
        size="small"
        :page="currentPage"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="[10, 20, 50]"
        show-size-picker
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
      <n-text v-else-if="isReadonly && showTable" depth="3" class="student-list-card__readonly-note">
        历史记录中的列表快照（只读）
      </n-text>
    </n-spin>

    <n-text v-if="isReadonly && !showTable" depth="3" class="student-list-card__readonly-note">
      该查询来自历史记录，无法再次刷新。
    </n-text>
  </div>
</template>

<style scoped>
.student-list-card {
  margin-top: 8px;
  padding: 12px 13px;
  border-radius: 8px;
  border: 1px solid #d7e3f4;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}

.student-list-card--error {
  border-color: #fecaca;
  background: #fef2f2;
}

.student-list-card--historical {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.student-list-card__title {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #1f4fbf;
}

.student-list-card--error .student-list-card__title {
  color: #b91c1c;
}

.student-list-card--historical .student-list-card__title {
  color: #4b5563;
}

.student-list-card__hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #374151;
}

.student-list-card__toolbar {
  margin-bottom: 8px;
}

.student-list-card__table-wrap {
  width: 100%;
}

.student-list-card__pagination {
  margin-top: 8px;
  justify-content: flex-end;
}

.student-list-card__readonly-note {
  display: block;
  margin-top: 6px;
  font-size: 12px;
}

.student-list-card :deep(.n-button--primary-type) {
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
