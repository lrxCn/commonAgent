import axios from "axios";

/** Shared HTTP client; dev requests go through Vite proxy to Back :8080. */
export const http = axios.create({
  baseURL: "",
  withCredentials: true,
});

let unauthorizedHandler: (() => void) | null = null;

/** Register 401 handler after Pinia/router are ready (see main.ts). */
export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler;
}

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      unauthorizedHandler
    ) {
      unauthorizedHandler();
    }
    return Promise.reject(error);
  },
);

export default http;
