<script setup lang="ts">
import { storeToRefs } from "pinia";
import { NButton, NCard, NSpace, NText } from "naive-ui";
import { useRouter } from "vue-router";

import { useCallStore } from "@/stores/call";

const router = useRouter();
const callStore = useCallStore();
const { incomingCall, hasIncoming } = storeToRefs(callStore);

let accepting = false;

async function onAccept(): Promise<void> {
  if (accepting || !incomingCall.value) {
    return;
  }
  accepting = true;
  try {
    await callStore.acceptIncoming();
    await router.push({ name: "app-calls" });
  } finally {
    accepting = false;
  }
}

function onReject(): void {
  callStore.rejectIncoming();
}
</script>

<template>
  <div v-if="hasIncoming && incomingCall" class="incoming-toast">
    <n-card size="small" :bordered="true" class="incoming-card">
      <n-space vertical :size="12">
        <n-text strong>来电</n-text>
        <n-text>{{ incomingCall.fromDisplayName }}</n-text>
        <n-space>
          <n-button type="primary" size="small" :loading="accepting" @click="onAccept">
            接听
          </n-button>
          <n-button size="small" @click="onReject">拒接</n-button>
        </n-space>
      </n-space>
    </n-card>
  </div>
</template>

<style scoped>
.incoming-toast {
  position: fixed;
  left: 16px;
  bottom: 16px;
  z-index: 2000;
  width: min(320px, calc(100vw - 32px));
}

.incoming-card {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
</style>
