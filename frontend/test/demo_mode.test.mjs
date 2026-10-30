import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

describe('Phase 6.4.1 Demo Safety & Disclaimer Tests', () => {
  it('HealthResponse interface defines demo_mode and rate_limit_enabled', () => {
    const apiPath = path.join(rootDir, 'src', 'lib', 'api.ts');
    const content = fs.readFileSync(apiPath, 'utf8');

    assert.match(
      content,
      /demo_mode\?: boolean;/,
      'HealthResponse should include optional demo_mode flag'
    );
    assert.match(
      content,
      /rate_limit_enabled\?: boolean;/,
      'HealthResponse should include optional rate_limit_enabled flag'
    );
  });

  it('page.tsx detects demo mode and displays the academic demonstration disclaimer', () => {
    const pagePath = path.join(rootDir, 'src', 'app', 'page.tsx');
    const content = fs.readFileSync(pagePath, 'utf8');

    assert.match(
      content,
      /isDemoMode/,
      'page.tsx should determine isDemoMode from backend health or environment'
    );
    assert.match(
      content,
      /Academic demonstration\. Do not upload confidential or personal information\./,
      'page.tsx must render the exact academic demonstration disclaimer'
    );
    assert.match(
      content,
      /Uploads and document deletions are disabled/,
      'page.tsx must explicitly warn that uploads and deletions are disabled'
    );
  });

  it('FileUpload component disables uploads and displays informative notice in demo mode', () => {
    const uploadPath = path.join(rootDir, 'src', 'components', 'FileUpload.tsx');
    const content = fs.readFileSync(uploadPath, 'utf8');

    assert.match(
      content,
      /isDemoMode\?: boolean;/,
      'FileUploadProps must accept isDemoMode prop'
    );
    assert.match(
      content,
      /Document Ingestion Disabled in Public Demo Mode/,
      'FileUpload must display ingestion disabled message when in demo mode'
    );
  });

  it('SearchInterface component blocks document deletion in demo mode', () => {
    const searchPath = path.join(rootDir, 'src', 'components', 'SearchInterface.tsx');
    const content = fs.readFileSync(searchPath, 'utf8');

    assert.match(
      content,
      /isDemoMode\?: boolean;/,
      'SearchInterfaceProps must accept isDemoMode prop'
    );
    assert.match(
      content,
      /Document deletion is disabled in public demo mode\./,
      'SearchInterface must block delete action when in demo mode'
    );
  });

  it('api.ts validates NEXT_PUBLIC_API_URL and prevents silent localhost fallback in production', () => {
    const apiPath = path.join(rootDir, 'src', 'lib', 'api.ts');
    const content = fs.readFileSync(apiPath, 'utf8');

    assert.match(
      content,
      /Production configuration error: NEXT_PUBLIC_API_URL is missing/,
      'api.ts must explicitly error in production if NEXT_PUBLIC_API_URL is missing'
    );
  });
});
