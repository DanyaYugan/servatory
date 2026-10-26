import { ref } from "vue";

export const user = ref(null);
export const csrf = ref("");
export const authChecked = ref(false);
export const version = ref("");
export const permissions = ref([]);

function errorFrom(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string") return new Error(detail);
  if (Array.isArray(detail)) {
    return new Error(detail.map((item) => item.msg || JSON.stringify(item)).join("; "));
  }
  return new Error(`HTTP ${status}`);
}

export async function request(url, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (csrf.value) headers["X-CSRF-Token"] = csrf.value;
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) {
    user.value = null;
  }
  if (!response.ok) throw errorFrom(body, response.status);
  return body;
}

export async function checkAuth() {
  try {
    const me = await request("/api/v1/auth/me");
    user.value = { login: me.login, role: me.role };
    permissions.value = me.permissions || [];
    csrf.value = me.csrf;
    const meta = await request("/api/v1/meta");
    version.value = meta.version || "";
  } catch {
    user.value = null;
  } finally {
    authChecked.value = true;
  }
}

export async function login(loginName, password) {
  const body = await request("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ login: loginName, password }),
  });
  user.value = { login: body.login, role: body.role };
  permissions.value = body.permissions || [];
  csrf.value = body.csrf;
  const meta = await request("/api/v1/meta");
  version.value = meta.version || "";
}

export async function logout() {
  try {
    await request("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // игнорируем: сессия могла уже истечь
  }
  user.value = null;
  permissions.value = [];
  csrf.value = "";
}


export function can(permission) {
  return permissions.value.includes(permission);
}
