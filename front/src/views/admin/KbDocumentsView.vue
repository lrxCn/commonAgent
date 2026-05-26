<script setup lang="ts">
import axios from "axios";
import { computed, h, onMounted, ref, watch } from "vue";
import {
  NButton,
  NDataTable,
  NDivider,
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

import { fetchRoles } from "@/api/admin";
import {
  createKbDocument,
  deleteKbDocument,
  fetchKbDocument,
  fetchKbDocuments,
  updateKbDocument,
} from "@/api/kb";
import type { AdminRole, ApiErrorBody, KbDocument, KbDocumentDetail } from "@/types";

const message = useMessage();

const loading = ref(false);
const documents = ref<KbDocument[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);

const keyword = ref("");
const roleFilter = ref<string | null>(null);
const roleOptions = ref<{ label: string; value: string }[]>([]);

const createDrawerVisible = ref(false);
const detailDrawerVisible = ref(false);
const formLoading = ref(false);
const detailLoading = ref(false);

const formRoleIds = ref<string[]>([]);
const formDocName = ref("");
const formContent = ref("");
const formDocId = ref("");

const detailDoc = ref<KbDocumentDetail | null>(null);
const editDocName = ref("");
const editRawContent = ref("");
const editRoleIds = ref<string[]>([]);

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function nextVersion(current: string): string {
  const parsed = Number.parseInt(current, 10);
  if (!Number.isNaN(parsed)) {
    return String(parsed + 1);
  }
  return `${current}-1`;
}

const columns = computed<DataTableColumns<KbDocument>>(() => [
  { title: "文档名称", key: "doc_name", width: 160, ellipsis: { tooltip: true } },
  { title: "doc_id", key: "doc_id", width: 160, ellipsis: { tooltip: true } },
  { title: "版本", key: "version", width: 80 },
  {
    title: "角色",
    key: "role_ids",
    width: 180,
    render: (row) =>
      h(
        NSpace,
        { size: 4, wrap: true },
        () =>
          row.role_ids.map((roleId) =>
            h(NTag, { size: "small", key: roleId }, { default: () => roleId }),
          ),
      ),
  },
  { title: "Chunks", key: "chunks_written", width: 90 },
  { title: "Tokens", key: "tokens_estimated", width: 90 },
  {
    title: "更新时间",
    key: "updated_at",
    width: 160,
    render: (row) => formatDateTime(row.updated_at),
  },
  {
    title: "操作",
    key: "actions",
    width: 180,
    render: (row) =>
      h(NSpace, { size: "small" }, () => [
        h(
          NButton,
          { size: "small", quaternary: true, type: "primary", onClick: () => openDetail(row) },
          { default: () => "详情" },
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => onDelete(row) },
          {
            trigger: () =>
              h(NButton, { size: "small", quaternary: true, type: "error" }, { default: () => "删除" }),
            default: () =>
              `确定删除文档「${row.doc_name}」（${row.role_ids.join("、")}）吗？此操作不可恢复。`,
          },
        ),
      ]),
  },
]);

async function loadRoles(): Promise<void> {
  try {
    const roles: AdminRole[] = await fetchRoles();
    roleOptions.value = roles.map((role) => ({
      label: `${role.name} (${role.role_id})`,
      value: role.role_id,
    }));
  } catch {
    roleOptions.value = [];
  }
}

async function loadDocuments(): Promise<void> {
  loading.value = true;
  try {
    const data = await fetchKbDocuments({
      offset: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      keyword: keyword.value.trim() || undefined,
      role_id: roleFilter.value || undefined,
    });
    documents.value = data.items;
    total.value = data.total;
  } catch {
    message.error("加载文档列表失败");
  } finally {
    loading.value = false;
  }
}

function resetCreateForm(): void {
  formRoleIds.value = [];
  formDocName.value = "";
  formContent.value = "";
  formDocId.value = "";
}

function openCreate(): void {
  resetCreateForm();
  createDrawerVisible.value = true;
}

async function openDetail(row: KbDocument): Promise<void> {
  detailDrawerVisible.value = true;
  detailLoading.value = true;
  detailDoc.value = null;
  try {
    const detail = await fetchKbDocument(row.doc_id);
    detailDoc.value = detail;
    editDocName.value = detail.doc_name;
    editRawContent.value = detail.raw_content;
    editRoleIds.value = [...detail.role_ids];
  } catch {
    message.error("加载文档详情失败");
    detailDrawerVisible.value = false;
  } finally {
    detailLoading.value = false;
  }
}

function extractFieldErrors(error: unknown): Record<string, string> {
  if (axios.isAxiosError(error) && error.response?.data) {
    const body = error.response.data as ApiErrorBody;
    return body.field_errors ?? {};
  }
  return {};
}

async function onCreateSubmit(): Promise<void> {
  if (formRoleIds.value.length === 0) {
    message.warning("请至少选择一个角色");
    return;
  }
  if (!formDocName.value.trim()) {
    message.warning("请填写文档名称");
    return;
  }
  if (!formContent.value.trim()) {
    message.warning("请填写文档内容或上传文件");
    return;
  }

  formLoading.value = true;
  try {
    await createKbDocument({
      role_ids: formRoleIds.value,
      doc_name: formDocName.value.trim(),
      content: formContent.value.trim(),
      doc_id: formDocId.value.trim() || undefined,
    });
    message.success("文档已上传并入库");
    createDrawerVisible.value = false;
    await loadDocuments();
  } catch (error: unknown) {
    const fieldErrors = extractFieldErrors(error);
    if (fieldErrors.content) {
      message.error(`内容：${fieldErrors.content}`);
    } else if (fieldErrors.doc_id) {
      message.error(`doc_id：${fieldErrors.doc_id}`);
    } else if (fieldErrors.role_ids) {
      message.error(`角色：${fieldErrors.role_ids}`);
    } else if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "上传失败");
    } else {
      message.error("上传失败");
    }
  } finally {
    formLoading.value = false;
  }
}

async function onDetailSave(): Promise<void> {
  if (!detailDoc.value) {
    return;
  }
  if (!editDocName.value.trim()) {
    message.warning("请填写文档名称");
    return;
  }
  if (!editRawContent.value.trim()) {
    message.warning("文档内容不能为空");
    return;
  }
  if (editRoleIds.value.length === 0) {
    message.warning("请至少选择一个角色");
    return;
  }

  formLoading.value = true;
  try {
    const updated = await updateKbDocument(detailDoc.value.doc_id, {
      role_ids: editRoleIds.value,
      doc_name: editDocName.value.trim(),
      raw_content: editRawContent.value.trim(),
      version: nextVersion(detailDoc.value.version),
    });
    message.success(`已保存为新版本 v${updated.version}`);
    detailDoc.value = { ...detailDoc.value, ...updated, chunks: detailDoc.value.chunks };
    await loadDocuments();
    const refreshed = await fetchKbDocument(updated.doc_id);
    detailDoc.value = refreshed;
    editDocName.value = refreshed.doc_name;
    editRawContent.value = refreshed.raw_content;
    editRoleIds.value = [...refreshed.role_ids];
  } catch (error: unknown) {
    const fieldErrors = extractFieldErrors(error);
    if (fieldErrors.content || fieldErrors.raw_content) {
      message.error(`内容：${fieldErrors.content ?? fieldErrors.raw_content}`);
    } else if (fieldErrors.role_ids) {
      message.error(`角色：${fieldErrors.role_ids}`);
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

async function onDelete(row: KbDocument): Promise<void> {
  try {
    await deleteKbDocument(row.doc_id);
    message.success("文档已删除");
    if (documents.value.length === 1 && page.value > 1) {
      page.value -= 1;
    }
    if (detailDoc.value?.doc_id === row.doc_id) {
      detailDrawerVisible.value = false;
      detailDoc.value = null;
    }
    await loadDocuments();
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "删除失败");
    } else {
      message.error("删除失败");
    }
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) {
    return;
  }
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext !== "txt" && ext !== "md") {
    message.warning("仅支持 .txt / .md 文件");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    formContent.value = String(reader.result ?? "");
    if (!formDocName.value.trim()) {
      formDocName.value = file.name.replace(/\.(txt|md)$/i, "");
    }
  };
  reader.onerror = () => {
    message.error("读取文件失败");
  };
  reader.readAsText(file, "utf-8");
}

function onSearch(): void {
  page.value = 1;
  void loadDocuments();
}

function onPageChange(nextPage: number): void {
  page.value = nextPage;
  void loadDocuments();
}

function onPageSizeChange(size: number): void {
  pageSize.value = size;
  page.value = 1;
  void loadDocuments();
}

watch(roleFilter, () => {
  page.value = 1;
  void loadDocuments();
});

onMounted(async () => {
  await loadRoles();
  await loadDocuments();
});
</script>

<template>
  <div class="kb-page">
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center" wrap>
        <n-space wrap>
          <n-select
            v-model:value="roleFilter"
            :options="roleOptions"
            placeholder="角色筛选"
            clearable
            filterable
            style="width: 220px"
          />
          <n-input
            v-model:value="keyword"
            placeholder="搜索 doc_name / doc_id"
            clearable
            style="width: 240px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <n-button type="primary" @click="onSearch">搜索</n-button>
        </n-space>
        <n-button type="primary" @click="openCreate">新建文档</n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="documents"
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
        :row-key="(row: KbDocument) => row.doc_id"
      />
    </n-space>

    <n-drawer v-model:show="createDrawerVisible" :width="480" placement="right">
      <n-drawer-content title="新建文档" closable>
        <n-form label-placement="top">
          <n-form-item label="角色" required>
            <n-select
              v-model:value="formRoleIds"
              :options="roleOptions"
              multiple
              filterable
              placeholder="至少选择一个角色"
            />
          </n-form-item>
          <n-form-item label="文档名称" required>
            <n-input v-model:value="formDocName" placeholder="例如 产品价目表" />
          </n-form-item>
          <n-form-item label="doc_id">
            <n-input v-model:value="formDocId" placeholder="可选，留空自动生成" />
          </n-form-item>
          <n-form-item label="文档内容" required>
            <n-input
              v-model:value="formContent"
              type="textarea"
              placeholder="粘贴正文，或通过下方上传 .txt / .md 文件"
              :autosize="{ minRows: 8, maxRows: 16 }"
            />
          </n-form-item>
          <n-form-item label="上传文件">
            <input type="file" accept=".txt,.md,text/plain,text/markdown" @change="onFileChange" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="createDrawerVisible = false">取消</n-button>
            <n-button type="primary" :loading="formLoading" @click="onCreateSubmit">
              上传并入库
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>

    <n-drawer v-model:show="detailDrawerVisible" :width="560" placement="right">
      <n-drawer-content title="文档详情" closable>
        <div v-if="detailLoading" class="detail-loading">加载中…</div>
        <template v-else-if="detailDoc">
          <n-space vertical :size="12">
            <n-space wrap>
              <n-tag size="small">doc_id: {{ detailDoc.doc_id }}</n-tag>
              <n-tag v-for="roleId in detailDoc.role_ids" :key="roleId" size="small">
                角色: {{ roleId }}
              </n-tag>
              <n-tag size="small">版本: v{{ detailDoc.version }}</n-tag>
              <n-tag size="small">Chunks: {{ detailDoc.chunks_written }}</n-tag>
              <n-tag size="small">Tokens: {{ detailDoc.tokens_estimated }}</n-tag>
            </n-space>
            <div class="meta-line">更新于 {{ formatDateTime(detailDoc.updated_at) }}</div>

            <n-form label-placement="top">
              <n-form-item label="角色" required>
                <n-select
                  v-model:value="editRoleIds"
                  :options="roleOptions"
                  multiple
                  filterable
                  placeholder="至少选择一个角色"
                />
              </n-form-item>
              <n-form-item label="文档名称" required>
                <n-input v-model:value="editDocName" />
              </n-form-item>
              <n-form-item label="正文（保存将触发新版本 ingest）" required>
                <n-input
                  v-model:value="editRawContent"
                  type="textarea"
                  :autosize="{ minRows: 10, maxRows: 20 }"
                />
              </n-form-item>
            </n-form>

            <n-divider>Chunk 概览</n-divider>
            <div v-if="detailDoc.chunks.length === 0" class="chunk-empty">暂无 chunk 数据</div>
            <div v-else class="chunk-list">
              <div v-for="chunk in detailDoc.chunks" :key="chunk.chunk_id" class="chunk-item">
                <div class="chunk-head">#{{ chunk.index }} · {{ chunk.chunk_id }}</div>
                <pre class="chunk-text">{{ chunk.text }}</pre>
              </div>
            </div>
          </n-space>
        </template>
        <template v-if="detailDoc && !detailLoading" #footer>
          <n-space justify="end">
            <n-button @click="detailDrawerVisible = false">关闭</n-button>
            <n-button type="primary" :loading="formLoading" @click="onDetailSave">
              保存新版本
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.kb-page {
  width: 100%;
}

.detail-loading {
  color: #666;
  padding: 24px 0;
}

.meta-line {
  font-size: 13px;
  color: #666;
}

.chunk-empty {
  color: #999;
  font-size: 13px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 280px;
  overflow-y: auto;
}

.chunk-item {
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fafafa;
}

.chunk-head {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.chunk-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  font-family: inherit;
}
</style>
