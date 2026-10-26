import { createRouter, createWebHistory } from "vue-router";

import Dashboard from "./views/Dashboard.vue";
import Install from "./views/Install.vue";
import Service from "./views/Service.vue";
import Settings from "./views/Settings.vue";

const routes = [
  { path: "/", name: "dashboard", component: Dashboard },
  { path: "/services/:name", name: "service", component: Service, props: true },
  { path: "/install", name: "install", component: Install },
  { path: "/settings", name: "settings", component: Settings },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

export default createRouter({
  history: createWebHistory("/ui/"),
  routes,
});
