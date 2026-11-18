import { apiClient, removeStoredToken, setStoredToken } from "@/lib/api-client";
import { AuthResponse, User } from "@/types";

export const authService = {
  async register(email: string, fullName: string, password: string): Promise<AuthResponse> {
    const data = await apiClient<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        full_name: fullName,
        password,
      }),
    });
    if (data.access_token) {
      setStoredToken(data.access_token);
    }
    return data;
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const data = await apiClient<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
      }),
    });
    if (data.access_token) {
      setStoredToken(data.access_token);
    }
    return data;
  },

  async getMe(): Promise<User> {
    return apiClient<User>("/api/v1/auth/me");
  },

  logout(): void {
    removeStoredToken();
  },
};
