<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  NAlert,
  NButton,
  NDataTable,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
} from "naive-ui";

import { useCallStore } from "@/stores/call";
import type { CallPeer } from "@/types/call";

const message = useMessage();
const callStore = useCallStore();
const {
  peers,
  peersLoading,
  phase,
  activeCall,
  wsConnected,
  notice,
  isOutgoing,
} = storeToRefs(callStore);

const statusAlert = computed(() => {
  if (isOutgoing.value && activeCall.value) {
    return {
      type: "info" as const,
      title: `正在呼叫 ${activeCall.value.peerDisplayName}…`,
      showCancel: true,
    };
  }
  if (phase.value === "in_call" && activeCall.value) {
    return {
      type: "success" as const,
      title: `与 ${activeCall.value.peerDisplayName} 通话中`,
      showCancel: false,
    };
  }
  return null;
});

function peerDisplayName(peer: CallPeer): string {
  return peer.display_name?.trim() || peer.username;
}

const columns = computed<DataTableColumns<CallPeer>>(() => [
  {
    title: "显示名",
    key: "display_name",
    render: (row) => peerDisplayName(row),
  },
  { title: "用户名", key: "username", width: 140 },
  {
    title: "操作",
    key: "actions",
    width: 120,
    render: (row) =>
      h(
        NButton,
        {
          size: "small",
          type: "primary",
          disabled: phase.value !== "idle" || !wsConnected.value,
          onClick: () => onInvite(row),
        },
        { default: () => "呼叫" },
      ),
  },
]);

async function loadPeers(): Promise<void> {
  try {
    await callStore.loadPeers();
  } catch {
    message.error("加载可呼叫用户失败");
  }
}

function onInvite(peer: CallPeer): void {
  try {
    callStore.invitePeer(peer);
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : "无法发起呼叫";
    message.error(text);
  }
}

function onCancelOutgoing(): void {
  try {
    callStore.cancelOutgoing();
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : "取消失败";
    message.error(text);
  }
}

watch(notice, (text) => {
  if (text) {
    message.warning(text);
    callStore.clearNotice();
  }
});

onMounted(async () => {
  callStore.connectSignaling();
  await loadPeers();
});

onUnmounted(() => {
  callStore.disconnectSignaling();
});
</script>

<template>
  <div class="calls-page">
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center" wrap>
        <h2 class="page-title">通话</h2>
        <n-tag :type="wsConnected ? 'success' : 'warning'" size="small" round>
          {{ wsConnected ? "信令已连接" : "信令连接中…" }}
        </n-tag>
      </n-space>

      <n-space v-if="statusAlert" vertical :size="8">
        <n-alert :type="statusAlert.type" :title="statusAlert.title" />
        <n-button
          v-if="statusAlert.showCancel"
          size="small"
          @click="onCancelOutgoing"
        >
          取消呼叫
        </n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="peers"
        :loading="peersLoading"
        :row-key="(row: CallPeer) => row.user_id"
      />
    </n-space>
  </div>
</template>

<style scoped>
.calls-page {
  width: 100%;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
</style>
