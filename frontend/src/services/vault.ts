import { apiRequest } from "./api";

export type VaultCredential = {
  id: string;
  site_name: string;
  site_url: string;
  masked_username: string;
  created_at: string;
  last_used_at: string | null;
};

export type VaultListResponse = {
  items: VaultCredential[];
};

export type VaultStorePayload = {
  site_name: string;
  site_url: string;
  username: string;
  password: string;
};

export async function listCredentials(): Promise<VaultListResponse> {
  return apiRequest<VaultListResponse>("/api/v1/vault/credentials");
}

export async function storeCredential(payload: VaultStorePayload): Promise<VaultCredential> {
  return apiRequest<VaultCredential>("/api/v1/vault/credentials", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteCredential(credentialId: string): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/v1/vault/credentials/${credentialId}`, {
    method: "DELETE",
  });
}
