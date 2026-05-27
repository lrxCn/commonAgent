<script setup lang="ts">
import axios from "axios";
import { computed, h, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
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
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center" wrap>
        <n-space wrap>
          <n-input
            v-model:value="search"
            placeholder="搜索姓名 / 学号 / 班级"
            clearable
            style="width: 240px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <n-select
            v-model:value="statusFilter"
            :options="statusOptions"
            placeholder="状态筛选"
            clearable
            style="width: 120px"
          />
          <n-select
            v-model:value="classFilter"
            :options="classOptions"
            placeholder="班级筛选"
            clearable
            filterable
            style="width: 160px"
          />
          <n-button type="primary" @click="onSearch">搜索</n-button>
        </n-space>
        <n-button type="primary" @click="openCreate">新建学生</n-button>
      </n-space>

      <n-data-table
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
    </n-space>

    <n-drawer v-model:show="drawerVisible" :width="400" placement="right">
      <n-drawer-content :title="editing ? '编辑学生' : '新建学生'" closable>
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
}
</style>
