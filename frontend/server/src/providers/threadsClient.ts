import { requireEnv } from '../env.js';

export interface ThreadsClientOptions {
  accessToken: string;
  userId: string;
  graphBaseUrl?: string;
}

export interface ThreadsPublishInput {
  text: string;
}

export interface ThreadsPublishResult {
  postId: string;
  creationId: string;
  raw: unknown;
}

export class ThreadsClient {
  private readonly graphBaseUrl: string;

  constructor(private readonly options: ThreadsClientOptions) {
    this.graphBaseUrl = options.graphBaseUrl ?? 'https://graph.threads.net/v1.0';
  }

  static fromEnv(): ThreadsClient {
    return new ThreadsClient({
      accessToken: requireEnv('THREADS_ACCESS_TOKEN'),
      userId: requireEnv('THREADS_USER_ID'),
      graphBaseUrl: process.env['THREADS_GRAPH_BASE_URL'],
    });
  }

  get userId(): string {
    return this.options.userId;
  }

  async publishTextPost(input: ThreadsPublishInput): Promise<ThreadsPublishResult> {
    const text = input.text.trim();
    if (!text) {
      throw new Error('Threads post text is required.');
    }
    if (text.length > 500) {
      throw new Error('Threads post text must be 500 characters or fewer.');
    }

    const creationId = await this.createTextContainer(text);
    const publishResponse = await this.publishContainer(creationId);

    return {
      postId: readStringField(publishResponse, 'id') ?? creationId,
      creationId,
      raw: publishResponse,
    };
  }

  private async createTextContainer(text: string): Promise<string> {
    const json = await this.postForm(`${this.graphBaseUrl}/${this.options.userId}/threads`, {
      media_type: 'TEXT',
      text,
    });
    const id = readStringField(json, 'id');
    if (!id) {
      throw new Error('Threads create container response did not include an id.');
    }
    return id;
  }

  private async publishContainer(creationId: string): Promise<unknown> {
    return this.postForm(`${this.graphBaseUrl}/${this.options.userId}/threads_publish`, {
      creation_id: creationId,
    });
  }

  private async postForm(url: string, fields: Record<string, string>): Promise<unknown> {
    const body = new URLSearchParams({
      ...fields,
      access_token: this.options.accessToken,
    });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    const json = (await response.json().catch(() => null)) as unknown;

    if (!response.ok) {
      throw new Error(`Threads API request failed (${response.status}): ${JSON.stringify(json)}`);
    }

    return json;
  }
}

function readStringField(value: unknown, field: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  return typeof record[field] === 'string' ? record[field] : null;
}

