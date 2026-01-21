export async function fetchModels() {
  const res = await fetch("/api/models");
  if (!res.ok) {
    throw new Error("Failed to load models");
  }
  return res.json();
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

export function streamLogs(jobId, fromIndex, onLine, onDone) {
  const url = `/api/jobs/${jobId}/logs?from_index=${fromIndex}`;
  const source = new EventSource(url);

  source.onmessage = (event) => {
    if (event.data) {
      onLine(event.data);
    }
  };

  source.onerror = () => {
    source.close();
    if (onDone) {
      onDone();
    }
  };

  return source;
}
