const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Project {
  id: number;
  name: string;
  brand_url: string;
  competitor_urls: string[];
  status: string;
  language: string;
  phase: string;
  created_at: string;
  updated_at: string;
  has_pptx: boolean;
  slide_count: number;
  file_count: number;
  comment_count: number;
  slides?: SlidePreview[];
  comments?: Comment[];
}

export interface SlidePreview {
  order: number;
  type: string;
  content: Record<string, unknown>;
  preview_url: string;
}

export interface Comment {
  id: number;
  slide_order: number | null;
  author: string;
  content: string;
  resolved: boolean;
  created_at?: string;
}

export interface ProgressEvent {
  step: string;
  message: string;
  done?: boolean;
  competitors?: { name: string; source: string; confidence: number; category_role?: string; reason?: string }[];
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/api/projects`);
  return res.json();
}

export async function getProject(id: number): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/projects/${id}`);
  return res.json();
}

export async function createProject(data: {
  name: string;
  brand_url: string;
  competitor_urls: string[];
  language: string;
  phase?: string;
}): Promise<Project> {
  const form = new FormData();
  form.append("name", data.name);
  form.append("brand_url", data.brand_url);
  form.append("competitor_urls", JSON.stringify(data.competitor_urls));
  form.append("language", data.language);
  if (data.phase) form.append("phase", data.phase);
  const res = await fetch(`${API_BASE}/api/projects`, { method: "POST", body: form });
  return res.json();
}

export async function uploadFile(projectId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/files`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export function generateReport(
  projectId: number,
  onProgress: (event: ProgressEvent) => void,
  onComplete: (data: { pptx_path: string; slide_count: number }) => void,
  onError: (msg: string) => void,
  phase: string = "full"
) {
  const form = new FormData();
  form.append("phase", phase);

  // Use fetch with POST for SSE
  fetch(`${API_BASE}/api/projects/${projectId}/generate`, { method: "POST", body: form })
    .then(async (res) => {
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const eventMatch = block.match(/^event: (\w+)/);
          const dataMatch = block.match(/^data: (.+)$/m);
          if (eventMatch && dataMatch) {
            const eventType = eventMatch[1];
            const data = JSON.parse(dataMatch[1]);
            if (eventType === "progress") onProgress(data);
            else if (eventType === "complete") onComplete(data);
            else if (eventType === "error") onError(data.message);
          }
        }
      }
    })
    .catch((err) => onError(err.message));
}

export async function getSlides(projectId: number): Promise<SlidePreview[]> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/slides`);
  const slides: SlidePreview[] = await res.json();
  return slides.map((s) => ({
    ...s,
    preview_url: s.preview_url?.startsWith("/") ? `${API_BASE}${s.preview_url}` : s.preview_url,
  }));
}

export function slidePreviewUrl(slideId: number): string {
  return `${API_BASE}/api/slides/${slideId}/preview`;
}

export async function addComment(
  projectId: number,
  data: { slide_order?: number; author: string; content: string }
) {
  const form = new FormData();
  if (data.slide_order !== undefined) form.append("slide_order", String(data.slide_order));
  form.append("author", data.author);
  form.append("content", data.content);
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/comments`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export async function getComments(projectId: number): Promise<Comment[]> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/comments`);
  return res.json();
}

export function downloadUrl(projectId: number): string {
  return `${API_BASE}/api/projects/${projectId}/download`;
}

export async function deleteProject(projectId: number): Promise<void> {
  await fetch(`${API_BASE}/api/projects/${projectId}`, { method: "DELETE" });
}

export async function updateProject(
  projectId: number,
  data: Partial<{ name: string; brand_url: string; competitor_urls: string; language: string; phase: string }>
): Promise<Project> {
  const form = new FormData();
  for (const [key, value] of Object.entries(data)) {
    if (value !== undefined) form.append(key, value);
  }
  const res = await fetch(`${API_BASE}/api/projects/${projectId}`, { method: "PATCH", body: form });
  return res.json();
}
