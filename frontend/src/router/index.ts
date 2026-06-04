import { createRouter, createWebHistory } from "vue-router";

import AdminView from "../views/AdminView.vue";
import ChatView from "../views/ChatView.vue";
import HomeView from "../views/HomeView.vue";


const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView
    },
    {
      path: "/chat",
      name: "chat",
      component: ChatView
    },
    {
      path: "/admin",
      name: "admin",
      component: AdminView
    }
  ]
});

export default router;
