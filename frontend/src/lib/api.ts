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
  doc_id?: string;
  total_chunks?: number;
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

export interface ChunkRecord {
  chunk_id: string;
  doc_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  page_number: number;
  start_char: number;
  end_char: number;
  char_count: number;
  word_count: number;
  boundary_type: string;
  is_approximate: boolean;
  created_at: string;
}

export interface SearchResult {
  chunk_id: string;
  doc_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  page_number: number;
  start_char: number;
  end_char: number;
  char_count: number;
  word_count: number;
  boundary_type: string;
  is_approximate: boolean;
  score: number;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResult[];
  latency_ms?: number;
  search_time_ms?: number;
  model_name?: string;
  model?: string;
  message?: string;
}

export interface DocumentSummary {
  doc_id: string;
  filename: string;
  file_type: string;
  total_chunks: number;
  total_pages: number;
  indexed_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface IndexStatsResponse {
  total_documents: number;
  total_chunks: number;
  total_vectors: number;
  dimension: number;
  embedding_model: string;
  model_license?: string;
  index_type: string;
  memory_usage_mb?: number;
  status?: string;
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

export async function uploadDocument(
  file: File,
  chunkSize: number = 500,
  chunkOverlap: number = 80
): Promise<DocumentExtractionResponse> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);

  const queryParams = new URLSearchParams({
    chunk_size: chunkSize.toString(),
    chunk_overlap: chunkOverlap.toString(),
  });

  try {
    const response = await fetch(`${baseUrl}/api/documents/upload?${queryParams.toString()}`, {
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

export async function searchDocuments(
  query: string,
  topK: number = 5,
  docId?: string,
  minScore: number = 0.0
): Promise<SearchResponse> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}/api/documents/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        top_k: topK,
        doc_id: docId || null,
        min_score: minScore,
      }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Search failed: server returned status ${response.status}`);
    }

    if (!response.ok) {
      throw new Error(data.detail || "Search request failed.");
    }

    return data;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
      throw new Error(`Backend offline: Unable to connect to ${baseUrl}/api/documents/search`);
    }
    throw err;
  }
}

export async function getIndexStats(): Promise<IndexStatsResponse> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents/index/stats`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch index stats: status ${response.status}`);
  }
  return response.json();
}

export async function listIndexedDocuments(): Promise<DocumentSummary[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch indexed documents: status ${response.status}`);
  }
  return response.json();
}

export async function getDocumentChunks(docId: string): Promise<ChunkRecord[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents/${docId}/chunks`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch chunks for document ${docId}: status ${response.status}`);
  }
  return response.json();
}

export async function deleteIndexedDocument(docId: string): Promise<{ success: boolean; message: string; doc_id: string }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents/${docId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to delete document: status ${response.status}`);
  }
  return response.json();
}
