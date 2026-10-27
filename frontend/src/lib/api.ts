export interface DocumentPage {
  page_number: number;
  text: string;
  char_count: number;
  word_count: number;
  is_approximate?: boolean;
  boundary_type?: string;
}

export interface DocumentExtractionResponse {
  success: boolean;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  file_size_formatted: string;
  total_pages: number;
  total_characters: number;
  total_words: number;
  preview_text: string;
  extracted_pages: DocumentPage[];
  metadata: Record<string, any>;
  is_sample?: boolean;
  message: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  max_upload_size_mb: number;
  supported_formats: string[];
}

export interface ValidationResult {
  is_valid: boolean;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  error?: string | null;
}

const getApiBaseUrl = (): string => {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

export async function checkBackendHealth(): Promise<HealthResponse> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}/health`, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Backend health check failed with status: ${response.status}`);
    }

    return response.json();
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
      throw new Error(`Backend offline: Unable to connect to ${baseUrl}/health`);
    }
    throw err;
  }
}

export async function uploadDocument(file: File): Promise<DocumentExtractionResponse> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${baseUrl}/api/documents/upload`, {
      method: "POST",
      body: formData,
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Server returned status ${response.status} with non-JSON response.`);
    }

    if (!response.ok) {
      throw new Error(data.detail || data.message || `Upload failed with status ${response.status}`);
    }

    return data;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
      throw new Error(`Backend connection failure: Could not connect to FastAPI server at ${baseUrl}. Ensure backend is running.`);
    }
    throw err;
  }
}

export async function validateDocument(file: File): Promise<ValidationResult> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${baseUrl}/api/documents/validate`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  return data;
}
