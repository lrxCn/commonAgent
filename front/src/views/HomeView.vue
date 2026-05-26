<script setup lang="ts">
import { NCard, NConfigProvider, NH1, NLayout, NLayoutContent, NText } from "naive-ui";
</script>

<template>
  <n-config-provider>
    <n-layout style="min-height: 100vh">
      <n-layout-content style="padding: 24px">
        <n-card>
          <n-h1>commonAgent 演示平台</n-h1>
          <n-text depth="3">Front Vue3 SPA 脚手架已就绪。登录与业务页见后续任务。</n-text>
        </n-card>
      </n-layout-content>
    </n-layout>
  </n-config-provider>
</template>
