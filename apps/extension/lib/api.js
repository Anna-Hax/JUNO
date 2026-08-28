/** Loopback HTTP helpers for Juno serve (ADR-05). Depends on JunoConfig. */
const JunoApi = {
  /** @param {string} token */
  authHeaders(token) {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  },

  /**
   * @param {string} apiBaseUrl
   * @param {string} token
   * @returns {Promise<{ ok: boolean; status: number; body: object }>}
   */
  async getStatus(apiBaseUrl, token) {
    const resp = await fetch(`${apiBaseUrl}/status`, {
      headers: JunoApi.authHeaders(token),
    });
    const body = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, body };
  },

  /**
   * @param {string} apiBaseUrl
   * @param {string} token
   * @param {object} payload
   * @returns {Promise<{ ok: boolean; status: number; body: object }>}
   */
  async postIngest(apiBaseUrl, token, payload) {
    const resp = await fetch(`${apiBaseUrl}/ingest`, {
      method: "POST",
      headers: JunoApi.authHeaders(token),
      body: JSON.stringify(payload),
    });
    const body = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, body };
  },
};
