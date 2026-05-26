<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NSpace,
  NText,
  useMessage,
  type InputInst,
} from "naive-ui";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const loading = ref(false);
const passwordInputRef = ref<InputInst | null>(null);

function focusPassword(): void {
  passwordInputRef.value?.focus();
}

const redirectPath = computed(() => {
  const redirect = route.query.redirect;
  return typeof redirect === "string" && redirect.startsWith("/app")
    ? redirect
    : "/app/home";
});

async function onSubmit(): Promise<void> {
  if (!username.value.trim() || !password.value) {
    message.warning("请输入用户名和密码");
    return;
  }

  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    await router.replace(redirectPath.value);
  } catch {
    message.error("用户名或密码错误");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <n-card class="login-card" title="commonAgent 演示平台">
      <n-text depth="3">使用演示账号登录以继续</n-text>
      <n-form style="margin-top: 24px" @submit.prevent="onSubmit">
        <n-form-item label="用户名">
          <n-input
            v-model:value="username"
            placeholder="admin"
            autocomplete="username"
            :disabled="loading"
            @keyup.enter="focusPassword"
          />
        </n-form-item>
        <n-form-item label="密码">
          <n-input
            ref="passwordInputRef"
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="请输入密码"
            autocomplete="current-password"
            :disabled="loading"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-space justify="end">
          <n-button type="primary" attr-type="submit" :loading="loading">
            登录
          </n-button>
        </n-space>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f5f7fa;
}

.login-card {
  width: 100%;
  max-width: 400px;
}
</style>
