import { describeHealth } from "../core/version.js";
import { getHealth } from "../api/client.js";

export async function showBackendStatus(el) {
  try {
    el.textContent = describeHealth(await getHealth());
  } catch {
    el.textContent = describeHealth(null);
  }
}
