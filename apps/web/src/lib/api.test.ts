import { describe, expect, it, vi, afterEach } from "vitest";

import { deleteChatConversation } from "./api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("treats 204 No Content responses as successful void results", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteChatConversation("conversation-1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/chat/conversations/conversation-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
