<script setup lang="ts">
import { RouterView } from "vue-router";
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  type GlobalThemeOverrides,
  zhCN,
  dateZhCN,
} from "naive-ui";

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#2563EB",
    primaryColorHover: "#1D4ED8",
    primaryColorPressed: "#1E40AF",
    primaryColorSuppl: "#2563EB",
    borderRadius: "8px",
    borderColor: "#E2E8F0",
    tableColor: "#FFFFFF",
    bodyColor: "#F3F6FA",
    textColorBase: "#111827",
    textColor2: "#334155",
    textColor3: "#64748B",
  },
  Button: {
    borderRadiusSmall: "7px",
    borderRadiusMedium: "8px",
    heightMedium: "36px",
    paddingMedium: "0 14px",
    fontWeight: "600",
  },
  DataTable: {
    borderRadius: "10px",
    thColor: "#F8FAFC",
    thTextColor: "#475569",
    tdColor: "#FFFFFF",
    tdColorHover: "#F8FAFC",
    borderColor: "#E2E8F0",
  },
  Input: {
    borderRadius: "8px",
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: "8px",
      },
    },
  },
  Tag: {
    borderRadius: "999px",
  },
};
</script>

<template>
  <n-config-provider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme-overrides="themeOverrides"
  >
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
