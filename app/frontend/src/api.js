const MODEL_CONFIG_FALLBACK = [
  {
    model_type: "general",
    model_size_gb: 3.5,
    kv_per_1k_ctx_gb: 0.35,
    default_num_ctx: 4096,
    min_num_ctx: 1024,
    max_num_ctx: 8192
  },
  {
    model_type: "translation",
    model_size_gb: 5.7,
    kv_per_1k_ctx_gb: 0.22,
    default_num_ctx: 3072,
    min_num_ctx: 1024,
    max_num_ctx: 8192
  }
];

export async function fetchModels() {
  const res = await fetch("/api/models");
  if (!res.ok) {
    throw new Error("Failed to load models");
  }
  return res.json();
}

export async function fetchProfiles() {
  const res = await fetch("/api/profiles");
  if (!res.ok) {
    throw new Error("Failed to load profiles");
  }
  return res.json();
}

export async function fetchModelConfig() {
  try {
    const res = await fetch("/api/model-config");
    if (!res.ok) {
      throw new Error("Failed to load model config");
    }
    const payload = await res.json();
    if (Array.isArray(payload) && payload.length > 0) {
      return payload;
    }
  } catch (err) {
    console.warn("Failed to fetch model config, using fallback:", err);
  }
  return MODEL_CONFIG_FALLBACK;
}

export async function createJob(formData) {
  const res = await fetch("/api/jobs", {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Failed to create job");
  }
  return res.json();
}

export async function fetchJobStatus(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error("Failed to fetch job status");
  }
  return res.json();
}

export async function cancelJob(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to cancel job");
  }
  return res.json();
}

export async function fetchRouteInfo(targets) {
  if (!targets || targets.length === 0) return { routes: [] };
  const query = targets.join(",");
  try {
    const res = await fetch(`/api/route-info?targets=${encodeURIComponent(query)}`);
    if (!res.ok) return { routes: [] };
    return res.json();
  } catch {
    return { routes: [] };
  }
}

export async function fetchTermStats() {
  const res = await fetch("/api/terms/stats");
  if (!res.ok) throw new Error("Failed to fetch term stats");
  return res.json();
}

export function getTermExportUrl(format, status) {
  const params = new URLSearchParams({ format });
  if (status && status !== "all") params.set("status", status);
  return `/api/terms/export?${params}`;
}

export async function fetchApprovedTerms(targetLang, domain) {
  const params = new URLSearchParams();
  if (targetLang) params.set("target_lang", targetLang);
  if (domain) params.set("domain", domain);
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(`/api/terms/approved${qs}`);
  if (!res.ok) throw new Error("Failed to fetch approved terms");
  return res.json();
}

export async function editTerm(sourceText, targetLang, domain, targetText, confidence) {
  const body = { source_text: sourceText, target_lang: targetLang, domain, target_text: targetText };
  if (confidence !== undefined) body.confidence = confidence;
  const res = await fetch("/api/terms/edit", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to edit term");
  return res.json();
}

export async function fetchUnverifiedTerms(targetLang, domain) {
  const params = new URLSearchParams();
  if (targetLang) params.set("target_lang", targetLang);
  if (domain) params.set("domain", domain);
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(`/api/terms/unverified${qs}`);
  if (!res.ok) throw new Error("Failed to fetch unverified terms");
  return res.json();
}

export async function approveTerm(sourceText, targetLang, domain) {
  const res = await fetch("/api/terms/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_text: sourceText, target_lang: targetLang, domain }),
  });
  if (!res.ok) throw new Error("Failed to approve term");
  return res.json();
}

export async function importTerms(file, strategy = "skip") {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`/api/terms/import?strategy=${encodeURIComponent(strategy)}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Import failed");
  }
  return res.json();
}
