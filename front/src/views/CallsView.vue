<script setup lang="ts">
import { computed, h, onUnmounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  NAlert,
  NButton,
  NDataTable,
  NSpace,
  NTag,
  NText,
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
  isInCall,
  remoteStream,
  callStartedAt,
} = storeToRefs(callStore);

const remoteAudioRef = ref<HTMLAudioElement | null>(null);
const elapsedLabel = ref("00:00");
let elapsedTimer: ReturnType<typeof setInterval> | null = null;

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function startElapsedTimer(): void {
  stopElapsedTimer();
  const update = (): void => {
    if (callStartedAt.value === null) {
      elapsedLabel.value = "00:00";
      return;
    }
    elapsedLabel.value = formatElapsed(Date.now() - callStartedAt.value);
  };
  update();
  elapsedTimer = setInterval(update, 1000);
}

function stopElapsedTimer(): void {
  if (elapsedTimer !== null) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
  elapsedLabel.value = "00:00";
}

watch(
  remoteStream,
  (stream) => {
    const el = remoteAudioRef.value;
    if (!el) {
      return;
    }
    el.srcObject = stream;
    if (stream) {
      void el.play().catch(() => {
        // autoplay may require user gesture; accept button satisfies this
      });
    }
  },
  { immediate: true },
);

watch(isInCall, (inCall) => {
  if (inCall) {
    startElapsedTimer();
  } else {
    stopElapsedTimer();
  }
});

const statusAlert = computed(() => {
  if (isOutgoing.value && activeCall.value) {
    return {
      type: "info" as const,
      title: `正在呼叫 ${activeCall.value.peerDisplayName}…`,
      showCancel: true,
    };
  }
  if (isInCall.value && activeCall.value) {
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

function canCallPeer(peer: CallPeer): boolean {
  return (
    phase.value === "idle" &&
    wsConnected.value &&
    callStore.isPeerOnline(peer.user_id)
  );
}

const columns = computed<DataTableColumns<CallPeer>>(() => [
  {
    title: "显示名",
    key: "display_name",
    render: (row) => peerDisplayName(row),
  },
  { title: "用户名", key: "username", width: 140 },
  {
    title: "状态",
    key: "online",
    width: 88,
    render: (row) =>
      h(
        NTag,
        {
          size: "small",
          round: true,
          type: callStore.isPeerOnline(row.user_id) ? "success" : "default",
        },
        {
          default: () =>
            callStore.isPeerOnline(row.user_id) ? "在线" : "离线",
        },
      ),
  },
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
          disabled: !canCallPeer(row),
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

function onHangup(): void {
  try {
    callStore.hangup();
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : "挂断失败";
    message.error(text);
  }
}

watch(notice, (text) => {
  if (text) {
    message.warning(text);
    callStore.clearNotice();
  }
});

void loadPeers();

onUnmounted(() => {
  stopElapsedTimer();
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

      <n-space v-if="isInCall" vertical :size="8" class="in-call-panel">
        <n-text>通话时长 {{ elapsedLabel }}</n-text>
        <n-button type="error" size="small" @click="onHangup">挂断</n-button>
        <audio ref="remoteAudioRef" autoplay playsinline class="remote-audio" />
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

.in-call-panel {
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
}

.remote-audio {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
</style>
