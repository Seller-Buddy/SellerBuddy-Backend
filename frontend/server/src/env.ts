import * as fs from 'fs';
import * as path from 'path';

let loaded = false;

function parseEnvLine(line: string): [string, string] | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) return null;

  const eq = trimmed.indexOf('=');
  if (eq === -1) return null;

  const key = trimmed.slice(0, eq).trim();
  let value = trimmed.slice(eq + 1).trim();
  if (!key) return null;

  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }

  return [key, value];
}

function findEnvFile(startDir: string): string | null {
  let current = path.resolve(startDir);

  for (;;) {
    const candidate = path.join(current, '.env');
    if (fs.existsSync(candidate)) return candidate;

    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

export function loadEnv(startDir = process.cwd()): void {
  if (loaded) return;
  loaded = true;

  const envPath = findEnvFile(startDir);
  if (!envPath) return;

  const content = fs.readFileSync(envPath, 'utf-8');
  for (const line of content.split(/\r?\n/)) {
    const parsed = parseEnvLine(line);
    if (!parsed) continue;
    const [key, value] = parsed;
    process.env[key] ??= value;
  }
}

export function requireEnv(name: string): string {
  loadEnv();
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

