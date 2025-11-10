import { defineStore } from "pinia";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    token: null,
    isAuthenticated: false,
  }),
  actions: {
    setAuth(user, token) {
      this.user = user;
      this.token = token;
      this.isAuthenticated = true;
    },
    logout() {
      this.user = null;
      this.token = null;
      this.isAuthenticated = false;
    },
  },
});
