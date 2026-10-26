// Environment-based configuration (Vite inlines VITE_* variables at build time).
export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api",
};
