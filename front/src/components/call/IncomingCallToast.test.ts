import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import IncomingCallToast from "@/components/call/IncomingCallToast.vue";
import { useCallStore } from "@/stores/call";

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: "/app/calls",
      name: "app-calls",
      component: { template: "<div />" },
    },
  ],
});

const naiveStubs = {
  NCard: { template: "<div class='n-card'><slot /></div>" },
  NButton: {
    template: "<button @click=\"$emit('click')\"><slot /></button>",
  },
  NSpace: { template: "<div><slot /></div>" },
  NText: { template: "<span><slot /></span>" },
};

describe("IncomingCallToast", () => {
  it("renders incoming caller display name", () => {
    setActivePinia(createPinia());
    const store = useCallStore();
    store.incomingCall = {
      callId: "call-1",
      fromUserId: "user-bob",
      fromDisplayName: "Bob 演示",
    };
    store.phase = "incoming";

    const wrapper = mount(IncomingCallToast, {
      global: {
        plugins: [router],
        stubs: naiveStubs,
      },
    });

    expect(wrapper.text()).toContain("Bob 演示");
    expect(wrapper.text()).toContain("接听");
    expect(wrapper.text()).toContain("拒接");
  });

  it("hides when there is no incoming call", () => {
    setActivePinia(createPinia());
    const wrapper = mount(IncomingCallToast, {
      global: {
        plugins: [router],
        stubs: naiveStubs,
      },
    });

    expect(wrapper.find(".incoming-toast").exists()).toBe(false);
  });
});
