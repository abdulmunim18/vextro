import apiClient from "../api/httpClient";

export async function createAssistantConversation(payload = {}) {
  const response = await apiClient.post(
    "/assistant/conversations",
    payload,
  );
  return response.data;
}

export async function getAssistantConversations() {
  const response = await apiClient.get(
    "/assistant/conversations",
  );
  return response.data;
}

export async function getAssistantConversation(conversationId) {
  const response = await apiClient.get(
    `/assistant/conversations/${conversationId}`,
  );
  return response.data;
}

export async function sendAssistantMessage(
  conversationId,
  content,
) {
  const response = await apiClient.post(
    `/assistant/conversations/${conversationId}/messages`,
    { content },
  );
  return response.data;
}
