import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./assets/main.css";
import "./assets/admin.css";
import { pinia } from "./stores/pinia";


const app = createApp(App);

app.use(pinia);
app.use(router);
app.mount("#app");
