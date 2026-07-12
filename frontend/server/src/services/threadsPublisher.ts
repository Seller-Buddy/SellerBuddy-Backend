import type { ThreadsPublishResult } from '../providers/threadsClient.js';
import { ThreadsClient } from '../providers/threadsClient.js';

export interface PublishApprovedThreadInput {
  draftText: string;
  approvedByOperator: boolean;
}

export async function publishApprovedThread(
  input: PublishApprovedThreadInput,
  client = ThreadsClient.fromEnv(),
): Promise<ThreadsPublishResult> {
  if (!input.approvedByOperator) {
    throw new Error('Operator approval is required before publishing to Threads.');
  }

  return client.publishTextPost({ text: input.draftText });
}
