// 登录态:token + 用户名(localStorage 持久)。鉴权语义归 B 轨;C 只负责附加请求头(04 任务书 §6)。

const TOKEN_KEY = 'harness-ui.token'
const USER_KEY = 'harness-ui.user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getSavedUser(): string {
  return localStorage.getItem(USER_KEY) ?? ''
}

export function setAuth(token: string, user: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, user)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
