<script setup lang="ts">
import axios from "axios";
import { computed, h, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  NButton,
  NCard,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NStatistic,
  NTag,
  useMessage,
  type DataTableColumns,
} from "naive-ui";

import {
  createStudent,
  deleteStudent,
  updateStudent,
} from "@/api/students";
import { useStudentsStore } from "@/stores/students";
import type { ApiErrorBody, Student } from "@/types";

const message = useMessage();
const studentsStore = useStudentsStore();
const {
  students,
  total,
  loading,
  page,
  pageSize,
  search,
  statusFilter,
  classFilter,
  classOptions,
  listRevision,
} = storeToRefs(studentsStore);

const drawerVisible = ref(false);
const editing = ref<Student | null>(null);
const formLoading = ref(false);
const formStudentNo = ref("");
const formName = ref("");
const formClassName = ref("");
const formStatus = ref("active");

const statusOptions = [
  { label: "在读", value: "active" },
  { label: "休学", value: "inactive" },
];

const statusLabelMap: Record<string, string> = {
  active: "在读",
  inactive: "休学",
};

const columns = computed<DataTableColumns<Student>>(() => [
  { title: "学号", key: "student_no", width: 120 },
  { title: "姓名", key: "name", width: 120 },
  { title: "班级", key: "class_name", width: 140, render: (row) => row.class_name || "—" },
  {
    title: "状态",
    key: "status",
    width: 100,
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
  {
    title: "操作",
    key: "actions",
    width: 160,
    render: (row) =>
      h(NSpace, { size: "small" }, () => [
        h(
          NButton,
          { size: "small", quaternary: true, type: "primary", onClick: () => openEdit(row) },
          { default: () => "编辑" },
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => onDelete(row.student_id) },
          {
            trigger: () =>
              h(NButton, { size: "small", quaternary: true, type: "error" }, { default: () => "删除" }),
            default: () => `确定删除学生「${row.name}」吗？`,
          },
        ),
      ]),
  },
]);

async function loadClassNames(): Promise<void> {
  await studentsStore.loadClassNames();
}

async function loadStudents(): Promise<void> {
  try {
    await studentsStore.loadStudents();
  } catch {
    message.error("加载学生列表失败");
  }
}

function resetForm(): void {
  formStudentNo.value = "";
  formName.value = "";
  formClassName.value = "";
  formStatus.value = "active";
}

function openCreate(): void {
  editing.value = null;
  resetForm();
  drawerVisible.value = true;
}

function openEdit(row: Student): void {
  editing.value = row;
  formStudentNo.value = row.student_no;
  formName.value = row.name;
  formClassName.value = row.class_name ?? "";
  formStatus.value = row.status;
  drawerVisible.value = true;
}

function extractFieldErrors(error: unknown): Record<string, string> {
  if (axios.isAxiosError(error) && error.response?.data) {
    const body = error.response.data as ApiErrorBody;
    return body.field_errors ?? {};
  }
  return {};
}

async function onSubmit(): Promise<void> {
  if (!formStudentNo.value.trim() || !formName.value.trim()) {
    message.warning("请填写学号和姓名");
    return;
  }

  formLoading.value = true;
  try {
    const payload = {
      student_no: formStudentNo.value.trim(),
      name: formName.value.trim(),
      class_name: formClassName.value.trim() || null,
      status: formStatus.value,
    };

    if (editing.value) {
      await updateStudent(editing.value.student_id, payload);
      message.success("学生信息已更新");
    } else {
      await createStudent(payload);
      message.success("学生已创建");
    }

    drawerVisible.value = false;
    await loadClassNames();
    await loadStudents();
  } catch (error: unknown) {
    const fieldErrors = extractFieldErrors(error);
    if (fieldErrors.student_no) {
      message.error(`学号冲突：${fieldErrors.student_no}`);
    } else if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "保存失败");
    } else {
      message.error("保存失败");
    }
  } finally {
    formLoading.value = false;
  }
}

async function onDelete(studentId: string): Promise<void> {
  try {
    await deleteStudent(studentId);
    message.success("已删除");
    if (students.value.length === 1 && page.value > 1) {
      page.value -= 1;
    }
    await loadClassNames();
    await loadStudents();
  } catch {
    message.error("删除失败");
  }
}

function onSearch(): void {
  page.value = 1;
  void loadStudents();
}

function onPageChange(nextPage: number): void {
  page.value = nextPage;
  void loadStudents();
}

function onPageSizeChange(size: number): void {
  pageSize.value = size;
  page.value = 1;
  void loadStudents();
}

watch([statusFilter, classFilter], () => {
  page.value = 1;
  void loadStudents();
});

watch(listRevision, (revision) => {
  if (revision > 0) {
    void studentsStore.refreshAfterExternalChange().catch(() => {
      message.error("加载学生列表失败");
    });
  }
});

onMounted(async () => {
  await loadClassNames();
  await loadStudents();
});
</script>

<template>
  <div class="students-page">
    <section class="students-hero">
      <div>
        <p class="students-hero__eyebrow">Student Management</p>
        <h1>学生管理</h1>
        <p>维护学生基础信息，支持智能对话内创建和查询。</p>
      </div>
      <n-button type="primary" size="medium" class="students-hero__button" @click="openCreate">
        新建学生
      </n-button>
    </section>

    <section class="students-stats">
      <n-card embedded :bordered="false" class="students-stat-card">
        <n-statistic label="学生总数" :value="total" />
      </n-card>
      <n-card embedded :bordered="false" class="students-stat-card">
        <n-statistic label="当前页" :value="page" />
      </n-card>
      <n-card embedded :bordered="false" class="students-stat-card">
        <n-statistic label="每页数量" :value="pageSize" />
      </n-card>
    </section>

    <section class="students-panel app-surface">
      <div class="students-toolbar">
        <div class="students-toolbar__filters">
          <n-input
            v-model:value="search"
            placeholder="搜索姓名 / 学号 / 班级"
            clearable
            class="students-filter students-filter--search"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <n-select
            v-model:value="statusFilter"
            :options="statusOptions"
            placeholder="状态筛选"
            clearable
            class="students-filter students-filter--status"
          />
          <n-select
            v-model:value="classFilter"
            :options="classOptions"
            placeholder="班级筛选"
            clearable
            filterable
            class="students-filter students-filter--class"
          />
        </div>
        <n-button type="primary" secondary class="students-search-button" @click="onSearch">
          搜索
        </n-button>
      </div>

      <n-data-table
        class="students-table"
        :columns="columns"
        :data="students"
        :loading="loading"
        :pagination="{
          page,
          pageSize,
          itemCount: total,
          showSizePicker: true,
          pageSizes: [10, 20, 50],
          onUpdatePage: onPageChange,
          onUpdatePageSize: onPageSizeChange,
        }"
        :row-key="(row: Student) => row.student_id"
      />
    </section>

    <n-drawer v-model:show="drawerVisible" :width="420" placement="right">
      <n-drawer-content
        :title="editing ? '编辑学生' : '新建学生'"
        closable
        :body-content-style="{ padding: '20px 22px' }"
      >
        <n-form label-placement="top">
          <n-form-item label="学号" required>
            <n-input v-model:value="formStudentNo" placeholder="例如 2024004" />
          </n-form-item>
          <n-form-item label="姓名" required>
            <n-input v-model:value="formName" placeholder="学生姓名" />
          </n-form-item>
          <n-form-item label="班级">
            <n-input v-model:value="formClassName" placeholder="例如 高一(1)班" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="formStatus" :options="statusOptions" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" :loading="formLoading" @click="onSubmit">
              保存
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.students-page {
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
}

.students-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.students-hero__eyebrow {
  margin: 0 0 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.students-hero h1 {
  margin: 0;
  color: #111827;
  font-size: 26px;
  line-height: 1.25;
  letter-spacing: 0;
}

.students-hero p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.students-hero__button {
  flex-shrink: 0;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.students-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.students-stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
}

.students-panel {
  overflow: hidden;
}

.students-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.students-toolbar__filters {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.students-filter--search {
  width: min(280px, 100%);
}

.students-filter--status {
  width: 128px;
}

.students-filter--class {
  width: 168px;
}

.students-search-button {
  flex-shrink: 0;
}

.students-table {
  padding: 0 2px 2px;
}

.students-table :deep(.n-data-table-th) {
  font-weight: 600;
}

.students-table :deep(.n-data-table-td) {
  height: 50px;
}

.students-table :deep(.n-pagination) {
  padding: 12px 14px 14px;
}

@media (max-width: 760px) {
  .students-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .students-stats {
    grid-template-columns: 1fr;
  }

  .students-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .students-filter--search,
  .students-filter--status,
  .students-filter--class,
  .students-search-button {
    width: 100%;
  }
}
</style>
