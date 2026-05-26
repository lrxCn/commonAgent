import axios from "axios";

/** Shared HTTP client; dev requests go through Vite proxy to Back :8080. */
export const http = axios.create({
  baseURL: "",
  withCredentials: true,
});

export default http;
