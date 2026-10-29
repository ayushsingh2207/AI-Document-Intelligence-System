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
  demo_mode?: boolean;
  rate_limit_enabled?: boolean;
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
  retrieval_strategy?: string;
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

export interface BM25StatsResponse {
  total_entries: number;
  unique_documents: number;
  avg_document_length_tokens: number;
  algorithm: string;
  license: string;
}

export type RetrievalStrategy = "dense" | "bm25" | "hybrid";

export interface Citation {
  citation_id: string;
  doc_id: string;
  filename: string;
  page_number: number;
  chunk_id: string;
  start_char: number;
  end_char: number;
  supporting_excerpt: string;
  boundary_type: string;
  is_approximate: boolean;
  relevance_score: number;
}

export interface QARequest {
  question: string;
  doc_id?: string | null;
  top_k?: number;
  confidence_threshold?: number;
}

export interface QAResponse {
  question: string;
  answered: boolean;
  answer: string;
  confidence: number;
  abstention_reason?: string | null;
  citations: Citation[];
  retrieval_strategy: string;
  latency_ms: number;
}

export interface ClauseSpan {
  category: string;
  detected: boolean;
  extracted_text?: string | null;
  doc_id: string;
  filename: string;
  page_number?: number | null;
  start_char?: number | null;
  end_char?: number | null;
  is_approximate: boolean;
  boundary_type?: string | null;
  confidence_score: number;
  detection_status: "detected" | "not_detected";
  explanation: string;
}

export interface ContractAnalysisRequest {
  confidence_threshold?: number;
  categories?: string[];
}

export interface ContractAnalysisResponse {
  doc_id: string;
  filename: string;
  total_pages: number;
  total_chunks_scanned: number;
  categories_analyzed: number;
  clauses_detected_count: number;
  clauses_not_detected_count: number;
  disclaimer: string;
  results: ClauseSpan[];
  latency_ms: number;
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
  minScore: number = 0.0,
  strategy: RetrievalStrategy = "hybrid"
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
        strategy,
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

export async function getBM25Stats(): Promise<BM25StatsResponse> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents/index/bm25-stats`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch BM25 stats: status ${response.status}`);
  }
  return response.json();
}

export async function askQuestion(request: QARequest): Promise<QAResponse> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}/api/documents/qa`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: request.question,
        doc_id: request.doc_id || null,
        top_k: request.top_k ?? 5,
        confidence_threshold: request.confidence_threshold ?? 0.45,
      }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Q&A request failed: server returned status ${response.status} with non-JSON response.`);
    }

    if (!response.ok) {
      throw new Error(data.detail || data.message || `Q&A request failed with status ${response.status}`);
    }

    return data;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
      throw new Error(`Backend offline: Unable to connect to ${baseUrl}/api/documents/qa`);
    }
    throw err;
  }
}

export async function getContractCategories(): Promise<string[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/documents/contract/categories`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch contract categories: status ${response.status}`);
  }
  return response.json();
}

export async function analyzeContract(
  docId: string,
  options?: ContractAnalysisRequest
): Promise<ContractAnalysisResponse> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}/api/documents/${docId}/contract-analysis`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        confidence_threshold: options?.confidence_threshold ?? 3.0,
        categories: options?.categories || null,
      }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Contract analysis failed: server returned status ${response.status} with non-JSON response.`);
    }

    if (!response.ok) {
      throw new Error(data.detail || data.message || `Contract analysis failed with status ${response.status}`);
    }

    return data;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
      throw new Error(`Backend offline: Unable to connect to ${baseUrl}/api/documents/${docId}/contract-analysis`);
    }
    throw err;
  }
}
