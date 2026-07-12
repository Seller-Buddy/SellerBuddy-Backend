import { useRef, useState } from 'react';

import { Button } from './ui/Button.js';

interface AgentLogEntry {
  id: number;
  agent: string;
  message: string;
}

interface PendingThreadPost {
  id: number;
  content: string;
}

type ProductItem = Record<string, unknown>;
type CsInquiry = Record<string, unknown>;
type CsPolicy = Record<string, unknown>;

interface CsAnswerDraft {
  inquiryTitle: string;
  requestType: string;
  decision: string;
  risk: string;
  evidence: string[];
  missingFields: string[];
  answer: string;
}

type DepartmentId = 'marketing' | 'cs';

interface DepartmentConfig {
  id: DepartmentId;
  label: string;
  description: string;
  placeholder: string;
  receiverAgent: string;
}

const DEPARTMENTS: DepartmentConfig[] = [
  {
    id: 'marketing',
    label: '마케팅 부서',
    description: '상품 정보와 Threads 게시글 생성 요청을 입력하는 공간입니다.',
    placeholder:
      '{"name":"오버핏 후드티","price":39000,"features":["남녀공용","두꺼운 원단"]}',
    receiverAgent: 'ProductParserAgent',
  },
  {
    id: 'cs',
    label: 'CS 업무자동화 부서',
    description: '고객 문의 CSV를 업로드하고 답변 초안 생성 흐름을 확인하는 공간입니다.',
    placeholder: '예: 고객이 수령 4일 후 사이즈 교환을 문의했습니다.',
    receiverAgent: 'CSAutomationAgent',
  },
];
const THREAD_GENERATE_URL = '/api/threads/generate';
const THREAD_PUBLISH_URL = '/api/threads/publish';
const CS_POLICY_INGEST_URL = '/api/cs/policies/ingest';
const CS_POLICY_SEARCH_URL = '/api/cs/policies/search';
const CS_ANALYZE_URL = '/api/cs/analyze';

const DEPARTMENT_THEME: Record<
  DepartmentId,
  {
    color: string;
    softBg: string;
    activeBg: string;
  }
> = {
  marketing: {
    color: '#7c5cff',
    softBg: 'rgba(124, 92, 255, 0.18)',
    activeBg: 'rgba(91, 55, 255, 0.55)',
  },
  cs: {
    color: '#27c7d9',
    softBg: 'rgba(39, 199, 217, 0.16)',
    activeBg: 'rgba(24, 116, 132, 0.58)',
  },
};

const MARKETING_AGENT_IDS = {
  catalog: 100,
  parser: 101,
  insight: 102,
  writer: 103,
  review: 104,
} as const;

const CS_AGENT_IDS = {
  intake: 110,
  classifier: 111,
  infoCheck: 112,
  policy: 113,
  decision: 114,
  reply: 115,
  safety: 116,
} as const;

interface AgentCommandPanelProps {
  onAgentDialogue?: (agentId: number, message: string) => void;
}

export function AgentCommandPanel({ onAgentDialogue }: AgentCommandPanelProps) {
  const [activeDepartment, setActiveDepartment] = useState<DepartmentId>('marketing');
  const [isConsoleOpen, setIsConsoleOpen] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const publishingRef = useRef(false);
  const [pendingThreadPosts, setPendingThreadPosts] = useState<PendingThreadPost[]>([]);
  const [uploadedProducts, setUploadedProducts] = useState<ProductItem[]>([]);
  const [uploadedInquiries, setUploadedInquiries] = useState<CsInquiry[]>([]);
  const [uploadedPolicies, setUploadedPolicies] = useState<CsPolicy[]>([]);
  const [csAnswerDraft, setCsAnswerDraft] = useState<CsAnswerDraft | null>(null);
  const [isProductPanelOpen, setIsProductPanelOpen] = useState(true);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const inquiryInputRef = useRef<HTMLInputElement | null>(null);
  const policyInputRef = useRef<HTMLInputElement | null>(null);
  const [prompts, setPrompts] = useState<Record<DepartmentId, string>>({
    marketing: '',
    cs: '',
  });
  const [logsByDepartment, setLogsByDepartment] = useState<Record<DepartmentId, AgentLogEntry[]>>({
    marketing: [],
    cs: [],
  });

  const department = DEPARTMENTS.find((item) => item.id === activeDepartment) ?? DEPARTMENTS[0];
  const departmentTheme = DEPARTMENT_THEME[activeDepartment];
  const prompt = prompts[activeDepartment];
  const logs = logsByDepartment[activeDepartment];

  const appendLogs = (departmentId: DepartmentId, entries: Omit<AgentLogEntry, 'id'>[]) => {
    setLogsByDepartment((prev) => ({
      ...prev,
      [departmentId]: [
        ...prev[departmentId],
        ...entries.map((entry, index) => ({
          ...entry,
          id: Date.now() + index,
        })),
      ],
    }));
  };

  const say = (agentId: number, agent: string, message: string) => {
    onAgentDialogue?.(agentId, message);
    appendLogs('marketing', [{ agent, message }]);
  };

  const sayCs = (agentId: number, agent: string, message: string) => {
    onAgentDialogue?.(agentId, message);
    appendLogs('cs', [{ agent, message }]);
  };

  const generateThreadPosts = async (payload: unknown, label: string) => {
    if (isRunning) return;

    setIsRunning(true);
    setPendingThreadPosts([]);
    say(MARKETING_AGENT_IDS.catalog, 'ProductCatalogAgent', `${label} 상품이 선택됐어요.`);
    say(MARKETING_AGENT_IDS.parser, 'ProductParserAgent', '상품 정보를 정리해서 넘길게요.');

    try {
      const response = await fetch(THREAD_GENERATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const json = (await response.json().catch(() => null)) as unknown;

      if (!response.ok) {
        throw new Error(`Backend request failed (${response.status}): ${formatJson(json)}`);
      }

      appendLogs('marketing', [
        {
          agent: 'ShopBuddy Backend',
          message: formatJson(json),
        },
      ]);

      say(MARKETING_AGENT_IDS.insight, 'ProductInsightAgent', '타겟과 페인포인트를 확인했어요.');
      say(MARKETING_AGENT_IDS.writer, 'ThreadWriterAgent', 'Threads 게시글 후보를 작성했어요.');

      const contents = extractThreadContents(json);
      if (contents.length === 0) {
        appendLogs('marketing', [
          {
            agent: 'ThreadsPublisher',
            message: '게시할 content 값을 백엔드 응답에서 찾지 못했습니다.',
          },
        ]);
        return;
      }

      setPendingThreadPosts(
        contents.map((content, index) => ({
          id: Date.now() + index,
          content,
        })),
      );
      say(
        MARKETING_AGENT_IDS.review,
        'ContentReviewAgent',
        `${contents.length}개의 후보를 검토했어요. 승인할 게시글을 골라주세요.`,
      );
    } catch (error) {
      appendLogs('marketing', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : 'Backend request failed.',
        },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || isRunning) return;

    appendLogs(activeDepartment, [
      {
        agent: 'User',
        message: trimmed,
      },
    ]);
    setPrompts((prev) => ({ ...prev, [activeDepartment]: '' }));

    if (activeDepartment !== 'marketing') {
      appendLogs(activeDepartment, [
        {
          agent: department.receiverAgent,
          message: 'CS 업무자동화 로직은 왼쪽 CS 데이터 패널에서 실행해주세요.',
        },
      ]);
      return;
    }

    const productJson = parseJsonInput(trimmed);
    await generateThreadPosts(productJson, '상품 JSON');
  };

  const handleApprovePublish = async (post: PendingThreadPost) => {
    if (isPublishing || publishingRef.current) return;

    const content = normalizeThreadContent(post.content);
    if (!content) {
      appendLogs('marketing', [
        {
          agent: 'System',
          message: '게시할 content가 비어 있습니다.',
        },
      ]);
      return;
    }
    if (content.length > 500) {
      appendLogs('marketing', [
        {
          agent: 'System',
          message: `Threads 게시글은 500자 이하만 게시할 수 있습니다. 현재 ${content.length}자입니다.`,
        },
      ]);
      return;
    }

    publishingRef.current = true;
    setIsPublishing(true);
    appendLogs('marketing', [
      {
        agent: 'Boss',
        message: `게시글을 승인했습니다.\n\n${content}`,
      },
    ]);
    say(MARKETING_AGENT_IDS.review, 'ContentReviewAgent', '승인 확인했습니다. 게시로 넘길게요.');
    say(MARKETING_AGENT_IDS.writer, 'ThreadWriterAgent', '승인된 문구를 업로드 요청합니다.');

    try {
      const publishResponse = await fetch(THREAD_PUBLISH_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const publishJson = (await publishResponse.json().catch(() => null)) as unknown;

      if (!publishResponse.ok) {
        throw new Error(
          `Threads publish failed (${publishResponse.status}): ${formatJson(publishJson)}`,
        );
      }

      appendLogs('marketing', [
        {
          agent: 'ThreadsPublisher',
          message: formatJson(publishJson),
        },
      ]);
      say(MARKETING_AGENT_IDS.catalog, 'ProductCatalogAgent', '게시 완료 상태로 기록해둘게요.');
      setPendingThreadPosts((prev) => prev.filter((item) => item.id !== post.id));
    } catch (error) {
      appendLogs('marketing', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : 'Threads publish failed.',
        },
      ]);
    } finally {
      publishingRef.current = false;
      setIsPublishing(false);
    }
  };

  const handleRejectPublish = (post: PendingThreadPost) => {
    setPendingThreadPosts((prev) => prev.filter((item) => item.id !== post.id));
    appendLogs('marketing', [
      {
        agent: 'Boss',
        message: `게시글을 거절했습니다. Threads에는 게시하지 않습니다.\n\n${post.content}`,
      },
    ]);
    say(MARKETING_AGENT_IDS.review, 'ContentReviewAgent', '거절 확인했습니다. 이 후보는 제외할게요.');
  };

  const handlePendingThreadContentChange = (postId: number, content: string) => {
    setPendingThreadPosts((prev) =>
      prev.map((item) => (item.id === postId ? { ...item, content } : item)),
    );
  };

  const handleProductListUpload = async (file: File | null) => {
    if (!file) return;

    try {
      const text = await readTextFile(file);
      const payload = parseProductListFile(file.name, text);
      setUploadedProducts(payload.products);
      setPendingThreadPosts([]);
      setActiveDepartment('marketing');
      say(
        MARKETING_AGENT_IDS.catalog,
        'ProductCatalogAgent',
        `${file.name}에서 ${payload.products.length}개 상품을 불러왔어요.`,
      );
    } catch (error) {
      appendLogs('marketing', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : '상품 리스트 업로드에 실패했습니다.',
        },
      ]);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleCsInquiryUpload = async (file: File | null) => {
    if (!file) return;

    try {
      const rows = await parseCsvFile(file);
      setUploadedInquiries(rows);
      setActiveDepartment('cs');
      setCsAnswerDraft(null);
      sayCs(
        CS_AGENT_IDS.intake,
        'InquiryIntakeAgent',
        `${rows.length}개의 문의를 접수했어요.`,
      );
      sayCs(
        CS_AGENT_IDS.classifier,
        'InquiryClassifierAgent',
        '문의 유형을 분류할 준비가 됐습니다.',
      );
      appendLogs('cs', [
        {
          agent: 'InquiryClassifierAgent',
          message: `${file.name} 파일에서 ${rows.length}개의 고객 문의를 불러왔습니다.`,
        },
      ]);
    } catch (error) {
      appendLogs('cs', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : '고객 문의 CSV 업로드에 실패했습니다.',
        },
      ]);
    } finally {
      if (inquiryInputRef.current) inquiryInputRef.current.value = '';
    }
  };

  const handleCsPolicyUpload = async (file: File | null) => {
    if (!file || isRunning) return;

    setIsRunning(true);
    try {
      const rows = await parseCsvFile(file);
      const documents = normalizePolicyDocuments(rows);
      if (documents.length === 0) {
        throw new Error('정책 CSV에서 title/content로 변환할 수 있는 데이터를 찾지 못했습니다.');
      }
      sayCs(CS_AGENT_IDS.policy, 'PolicySearchAgent', '정책 문서를 Chroma DB에 넣는 중입니다.');
      const json = await postJson(CS_POLICY_INGEST_URL, {
        documents,
        reset_collection: true,
      });
      setUploadedPolicies(rows);
      setActiveDepartment('cs');
      setCsAnswerDraft(null);
      sayCs(
        CS_AGENT_IDS.policy,
        'PolicySearchAgent',
        `${documents.length}개의 정책을 검색 가능한 상태로 저장했어요.`,
      );
      appendLogs('cs', [
        {
          agent: 'PolicySearchAgent',
          message: `${file.name} 파일에서 ${documents.length}개의 정책을 Chroma DB에 저장했습니다.`,
        },
        {
          agent: 'ShopBuddy Backend',
          message: formatJson(json),
        },
      ]);
    } catch (error) {
      appendLogs('cs', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : '정책 CSV 업로드에 실패했습니다.',
        },
      ]);
    } finally {
      if (policyInputRef.current) policyInputRef.current.value = '';
      setIsRunning(false);
    }
  };

  const handleCreateCsAnswer = async (inquiry: CsInquiry, index: number) => {
    if (isRunning) return;

    setCsAnswerDraft(null);
    setIsRunning(true);
    sayCs(CS_AGENT_IDS.intake, 'InquiryIntakeAgent', '새 고객 문의를 확인할게요.');
    sayCs(CS_AGENT_IDS.classifier, 'InquiryClassifierAgent', '반품, 교환, 배송 유형을 먼저 분류합니다.');
    sayCs(CS_AGENT_IDS.infoCheck, 'InfoCheckAgent', '수령일, 사용 여부, 택 제거 여부를 확인합니다.');
    appendLogs('cs', [
      {
        agent: 'CSAutomationAgent',
        message: `${readInquiryTitle(inquiry, index)} 문의가 선택됐습니다.`,
      },
      {
        agent: 'PolicySearchAgent',
        message: `${uploadedPolicies.length}개의 정책 CSV 데이터에서 관련 근거를 검색합니다.`,
      },
    ]);

    try {
      const customerMessage = readInquiryMessage(inquiry);
      const orderContext = buildOrderContext(inquiry);
      sayCs(CS_AGENT_IDS.policy, 'PolicySearchAgent', '관련 쇼핑몰 정책을 검색합니다.');
      const searchJson = await postJson(CS_POLICY_SEARCH_URL, {
        query: customerMessage,
        category: readNullableString(inquiry, ['request_type', 'category', 'type']),
        order_context: orderContext,
        top_k: 3,
      });
      appendLogs('cs', [
        {
          agent: 'PolicySearchAgent',
          message: formatJson(searchJson),
        },
      ]);

      const analyzeJson = await postJson(CS_ANALYZE_URL, {
        customer_message: customerMessage,
        order_context: orderContext,
      });
      const analyzeRecord = asRecord(analyzeJson) ?? {};
      const safetyReview = asRecord(analyzeRecord['safety_review']) ?? {};
      setCsAnswerDraft(mapCsAnalyzeResponse(analyzeJson, inquiry, index));
      sayCs(
        CS_AGENT_IDS.decision,
        'DecisionAgent',
        `${readString(analyzeRecord, ['decision_label', 'decision']) ?? '확인 필요'}로 판단했습니다.`,
      );
      sayCs(CS_AGENT_IDS.reply, 'ReplyWriterAgent', '고객에게 보낼 답변 초안을 작성했습니다.');
      sayCs(
        CS_AGENT_IDS.safety,
        'SafetyReviewAgent',
        `${readString(safetyReview, ['risk_level']) ?? 'unknown'} 위험도로 안전 검수를 마쳤습니다.`,
      );
      appendLogs('cs', [
        {
          agent: 'ReplyWriterAgent',
          message: '백엔드 분석 결과로 CS 답변 초안을 생성했습니다.',
        },
        {
          agent: 'SafetyReviewAgent',
          message: formatJson(analyzeJson),
        },
      ]);
    } catch (error) {
      appendLogs('cs', [
        {
          agent: 'System',
          message: error instanceof Error ? error.message : 'CS 분석 요청에 실패했습니다.',
        },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleCopyCsAnswer = async () => {
    if (!csAnswerDraft) return;
    await navigator.clipboard.writeText(csAnswerDraft.answer);
    appendLogs('cs', [
      {
        agent: 'OperatorApprovalAgent',
        message: '답변 초안을 클립보드에 복사했습니다.',
      },
    ]);
  };

  const showProductPanel = activeDepartment === 'marketing' && isProductPanelOpen;
  const showCsPanel = activeDepartment === 'cs' && isProductPanelOpen;

  return (
    <>
      {!isConsoleOpen && (
        <Button
          variant="active"
          size="sm"
          onClick={() => setIsConsoleOpen(true)}
          className="absolute right-10 bottom-10 z-50 px-8! py-4! text-xs shadow-pixel"
        >
          Agent Console
        </Button>
      )}

      {isConsoleOpen && showProductPanel && (
        <aside
          className="absolute top-10 right-[386px] bottom-10 z-50 w-320 max-w-[calc(100vw-410px)] pixel-panel p-8 flex flex-col gap-8"
          style={{ borderColor: DEPARTMENT_THEME.marketing.color }}
        >
          <div className="shrink-0 flex items-start justify-between gap-6">
            <div className="min-w-0">
              <h2
                className="m-0 text-sm leading-none"
                style={{ color: DEPARTMENT_THEME.marketing.color }}
              >
                상품 리스트
              </h2>
              <p className="m-0 mt-5 text-[10px] text-text-muted leading-tight">
                CSV 또는 JSON을 올리고 상품별 게시글을 생성합니다.
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsProductPanelOpen(false)}
              className="shrink-0 px-4! py-1! text-[10px] leading-tight"
            >
              닫기
            </Button>
          </div>

          <div className="shrink-0 flex items-center gap-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.csv,application/json,text/csv"
              className="hidden"
              onChange={(event) => void handleProductListUpload(event.target.files?.[0] ?? null)}
            />
            <Button
              variant="default"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 px-4! py-1! text-[10px] leading-tight"
            >
              업로드
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto flex flex-col gap-5 pr-2">
            {uploadedProducts.length === 0 ? (
              <div className="border border-border bg-bg-dark/70 p-8 text-[10px] text-text-muted leading-tight">
                상품 리스트를 업로드하면 이곳에 상품 카드가 표시됩니다.
              </div>
            ) : (
              uploadedProducts.map((product, index) => (
                <div key={index} className="border border-border bg-bg-dark/70 p-7">
                  <div className="flex items-start justify-between gap-6">
                    <div className="min-w-0">
                      <div className="text-xs text-accent-bright leading-tight truncate">
                        {readProductTitle(product, index)}
                      </div>
                      <div className="mt-4 text-[10px] text-text-muted leading-tight">
                        {readProductMeta(product)}
                      </div>
                      <div className="mt-4 text-[10px] text-text leading-tight max-h-28 overflow-hidden">
                        {readProductFeatures(product)}
                      </div>
                    </div>
                    <Button
                      variant={isRunning ? 'disabled' : 'active'}
                      size="sm"
                      onClick={() =>
                        void generateThreadPosts(
                          { products: [product] },
                          readProductTitle(product, index),
                        )
                      }
                      disabled={isRunning}
                      className="shrink-0 px-4! py-1! text-[10px] leading-tight"
                    >
                      생성
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      )}

      {isConsoleOpen && showCsPanel && (
        <aside
          className="absolute top-10 right-[386px] bottom-10 z-50 w-320 max-w-[calc(100vw-410px)] pixel-panel p-8 flex flex-col gap-8"
          style={{ borderColor: DEPARTMENT_THEME.cs.color }}
        >
          <div className="shrink-0 flex items-start justify-between gap-6">
            <div className="min-w-0">
              <h2 className="m-0 text-sm leading-none" style={{ color: DEPARTMENT_THEME.cs.color }}>
                CS 데이터
              </h2>
              <p className="m-0 mt-5 text-[10px] text-text-muted leading-tight">
                문의 CSV와 정책 CSV를 올리고 답변 초안을 생성합니다.
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsProductPanelOpen(false)}
              className="shrink-0 px-4! py-1! text-[10px] leading-tight"
            >
              닫기
            </Button>
          </div>

          <div className="shrink-0 grid grid-cols-2 gap-4">
            <input
              ref={inquiryInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => void handleCsInquiryUpload(event.target.files?.[0] ?? null)}
            />
            <input
              ref={policyInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => void handleCsPolicyUpload(event.target.files?.[0] ?? null)}
            />
            <Button
              variant={isRunning ? 'disabled' : 'default'}
              size="sm"
              onClick={() => inquiryInputRef.current?.click()}
              disabled={isRunning}
              className="px-4! py-1! text-[10px] leading-tight"
            >
              문의 업로드
            </Button>
            <Button
              variant={isRunning ? 'disabled' : 'default'}
              size="sm"
              onClick={() => policyInputRef.current?.click()}
              disabled={isRunning}
              className="px-4! py-1! text-[10px] leading-tight"
            >
              정책 업로드
            </Button>
          </div>

          <div className="shrink-0 grid grid-cols-2 gap-4 text-[10px] text-text-muted leading-tight">
            <div className="border border-border bg-bg-dark/70 p-5">
              문의 {uploadedInquiries.length}개
            </div>
            <div className="border border-border bg-bg-dark/70 p-5">
              정책 {uploadedPolicies.length}개
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto flex flex-col gap-5 pr-2">
            {uploadedInquiries.length === 0 ? (
              <div className="border border-border bg-bg-dark/70 p-8 text-[10px] text-text-muted leading-tight">
                고객 문의 CSV를 업로드하면 이곳에 문의 카드가 표시됩니다.
              </div>
            ) : (
              uploadedInquiries.map((inquiry, index) => (
                <div key={index} className="border border-border bg-bg-dark/70 p-7">
                  <div className="text-xs text-accent-bright leading-tight truncate">
                    {readInquiryTitle(inquiry, index)}
                  </div>
                  <div className="mt-4 text-[10px] text-text-muted leading-tight">
                    {readInquiryMeta(inquiry)}
                  </div>
                  <div className="mt-4 text-[10px] text-text leading-tight max-h-40 overflow-hidden">
                    {readInquiryMessage(inquiry)}
                  </div>
                  <Button
                    variant={uploadedPolicies.length === 0 || isRunning ? 'disabled' : 'active'}
                    size="sm"
                    onClick={() => void handleCreateCsAnswer(inquiry, index)}
                    disabled={uploadedPolicies.length === 0 || isRunning}
                    className="mt-6 w-full px-4! py-1! text-[10px] leading-tight"
                  >
                    {isRunning ? '처리 중...' : '답변 생성'}
                  </Button>
                </div>
              ))
            )}
          </div>
        </aside>
      )}

      {isConsoleOpen && (
        <aside
          className="absolute top-10 right-10 bottom-10 z-50 w-360 max-w-[calc(100vw-24px)] pixel-panel p-8 flex flex-col gap-8"
          style={{ borderColor: departmentTheme.color }}
        >
          <div className="shrink-0">
            <div className="flex items-start justify-between gap-6">
              <h2 className="m-0 text-lg leading-none" style={{ color: departmentTheme.color }}>
                Agent Console
              </h2>
              <div className="flex items-center gap-4">
                {(activeDepartment === 'marketing' || activeDepartment === 'cs') && (
                  <Button
                    variant={isProductPanelOpen ? 'active' : 'default'}
                    size="sm"
                    onClick={() => setIsProductPanelOpen((prev) => !prev)}
                    className="shrink-0 px-4! py-1! text-[10px] leading-tight"
                  >
                    {activeDepartment === 'marketing' ? '상품 목록' : 'CS 데이터'}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsConsoleOpen(false)}
                  className="shrink-0 px-4! py-1! text-[10px] leading-tight"
                >
                  닫기
                </Button>
              </div>
            </div>
            <p className="m-0 mt-5 text-[10px] text-text-muted leading-tight">
              {department.description}
            </p>
          </div>

          <div className="shrink-0 grid grid-cols-2 gap-4">
            {DEPARTMENTS.map((item) => {
              const itemTheme = DEPARTMENT_THEME[item.id];
              const isActive = activeDepartment === item.id;
              return (
                <Button
                  key={item.id}
                  variant={isActive ? 'active' : 'default'}
                  size="sm"
                  onClick={() => setActiveDepartment(item.id)}
                  className="px-3! py-2! text-[11px] leading-tight whitespace-normal min-h-40"
                  style={{
                    borderColor: isActive ? itemTheme.color : 'transparent',
                    background: isActive ? itemTheme.activeBg : undefined,
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto flex flex-col gap-6 pr-2">
            {logs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-[10px] text-text-muted leading-tight text-center px-10">
                {activeDepartment === 'marketing'
                  ? '상품 목록에서 상품을 선택하면 작업 로그가 표시됩니다.'
                  : 'CS 데이터를 업로드하고 문의를 선택하면 작업 로그가 표시됩니다.'}
              </div>
            ) : (
              logs.map((entry) => (
                <div key={entry.id} className="border border-border bg-bg-dark/70 p-7">
                  <div className="text-xs text-accent-bright leading-none">{entry.agent}</div>
                  <div className="mt-5 text-xs text-text leading-tight whitespace-pre-wrap">
                    {entry.message}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="shrink-0 flex flex-col gap-6">
            {activeDepartment === 'cs' && csAnswerDraft && (
              <div className="border-2 border-accent bg-bg-dark p-8">
                <div className="text-xs text-accent-bright leading-none">CS 답변 초안</div>
                <div className="mt-6 grid grid-cols-2 gap-4 text-[10px] text-text-muted leading-tight">
                  <div>판단: {csAnswerDraft.decision}</div>
                  <div>위험도: {csAnswerDraft.risk}</div>
                </div>
                <div className="mt-6 text-[10px] text-text-muted leading-tight">
                  정책 근거: {csAnswerDraft.evidence.join(' / ')}
                </div>
                {csAnswerDraft.missingFields.length > 0 && (
                  <div className="mt-5 text-[10px] text-accent-bright leading-tight">
                    추가 확인: {csAnswerDraft.missingFields.join(', ')}
                  </div>
                )}
                <textarea
                  value={csAnswerDraft.answer}
                  onChange={(event) =>
                    setCsAnswerDraft((prev) =>
                      prev ? { ...prev, answer: event.target.value } : prev,
                    )
                  }
                  className="mt-6 w-full h-120 resize-none bg-bg border-2 border-border text-text text-xs leading-tight p-7 outline-none focus:border-accent-bright"
                />
                <Button variant="active" size="sm" onClick={handleCopyCsAnswer} className="mt-6 w-full">
                  답변 복사
                </Button>
              </div>
            )}
            {activeDepartment === 'marketing' && pendingThreadPosts.length > 0 && (
              <div className="max-h-260 overflow-y-auto flex flex-col gap-6 pr-2">
                {pendingThreadPosts.map((post, index) => (
                  <div key={post.id} className="border-2 border-accent bg-bg-dark p-8">
                    <div className="text-xs text-accent-bright leading-none">
                      게시 전 승인 #{index + 1}
                    </div>
                    <textarea
                      value={post.content}
                      onChange={(event) =>
                        handlePendingThreadContentChange(post.id, event.target.value)
                      }
                      disabled={isPublishing}
                      className="mt-6 w-full h-140 resize-none bg-bg border-2 border-border text-text text-xs leading-tight p-7 outline-none focus:border-accent-bright disabled:opacity-60"
                    />
                    <div
                      className={`mt-4 text-[10px] leading-none ${
                        post.content.trim().length > 500 ? 'text-status-error' : 'text-text-muted'
                      }`}
                    >
                      {post.content.trim().length}/500자
                    </div>
                    <div className="mt-8 grid grid-cols-2 gap-4">
                      <Button
                        variant={
                          isPublishing || !post.content.trim() || post.content.trim().length > 500
                            ? 'disabled'
                            : 'active'
                        }
                        size="sm"
                        onClick={() => handleApprovePublish(post)}
                        disabled={
                          isPublishing || !post.content.trim() || post.content.trim().length > 500
                        }
                      >
                        승인
                      </Button>
                      <Button
                        variant={isPublishing ? 'disabled' : 'default'}
                        size="sm"
                        onClick={() => handleRejectPublish(post)}
                        disabled={isPublishing}
                      >
                        거절
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {activeDepartment === 'marketing' && (
              <>
                <textarea
                  value={prompt}
                  onChange={(event) =>
                    setPrompts((prev) => ({ ...prev, [activeDepartment]: event.target.value }))
                  }
                  placeholder={department.placeholder}
                  className="w-full h-120 resize-none bg-bg-dark border-2 border-border text-text text-xs leading-tight p-8 outline-none focus:border-accent-bright"
                />
                <Button
                  variant={isRunning ? 'disabled' : 'accent'}
                  onClick={handleSubmit}
                  disabled={isRunning}
                  className="w-full"
                >
                  {isRunning ? 'Running...' : `Send to ${department.label}`}
                </Button>
              </>
            )}
          </div>
        </aside>
      )}
    </>
  );
}
function parseJsonInput(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    throw new Error('입력값은 올바른 JSON이어야 합니다.');
  }
}

function parseProductListFile(fileName: string, text: string): { products: ProductItem[] } {
  const lowerName = fileName.toLowerCase();

  if (lowerName.endsWith('.json')) {
    const parsed = parseJsonInput(text);
    const record = asRecord(parsed);
    if (record && Array.isArray(record['products'])) {
      return { products: normalizeProductItems(record['products']) };
    }
    if (Array.isArray(parsed)) {
      return { products: normalizeProductItems(parsed) };
    }
    throw new Error('JSON 파일은 products 배열을 포함해야 합니다.');
  }

  if (lowerName.endsWith('.csv')) {
    const products = parseCsvProducts(text);
    if (products.length === 0) {
      throw new Error('CSV 파일에서 상품 데이터를 찾지 못했습니다.');
    }
    return { products };
  }

  throw new Error('지원하는 파일 형식은 .json 또는 .csv 입니다.');
}

async function parseCsvFile(file: File): Promise<Record<string, unknown>[]> {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('CSV 파일만 업로드할 수 있습니다.');
  }
  const text = await readTextFile(file);
  const rows = parseCsvRecords(text);
  if (rows.length === 0) {
    throw new Error('CSV 파일에서 데이터를 찾지 못했습니다.');
  }
  return rows;
}

async function readTextFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const utf8Text = new TextDecoder('utf-8').decode(buffer);
  if (!looksMojibake(utf8Text)) return utf8Text;

  try {
    const koreanText = new TextDecoder('euc-kr').decode(buffer);
    return looksMojibake(koreanText) ? utf8Text : koreanText;
  } catch {
    return utf8Text;
  }
}

function looksMojibake(value: string): boolean {
  return /�|ì|ë|ê|í|ã|怨|臾|諛|援|遺|寃|湲|쨌|곹|뺤|낅|덉|몄|뚯|섍|쒖|꾩|좏|묒/.test(
    value,
  );
}

function parseCsvRecords(text: string): Record<string, unknown>[] {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];

  const headers = rows[0].map((header) => header.trim()).filter(Boolean);
  if (headers.length === 0) return [];

  return rows
    .slice(1)
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row) => {
      const record: Record<string, unknown> = {};
      headers.forEach((header, index) => {
        const rawValue = row[index]?.trim() ?? '';
        record[header] = normalizeCsvValue(header, rawValue);
      });
      return record;
    });
}

function normalizeProductItems(items: unknown[]): ProductItem[] {
  return items
    .map((item) => asRecord(item))
    .filter((item): item is ProductItem => item !== null);
}

function normalizePolicyDocuments(
  rows: CsPolicy[],
): { title: string; content: string; category?: string | null; source?: string | null }[] {
  return rows
    .map((row, index) => {
      const title =
        readString(row, ['title', 'policy_title', 'name', 'policy_name']) ?? `정책 ${index + 1}`;
      const content =
        readString(row, ['content', 'policy_content', 'body', 'description', 'rule']) ??
        Object.entries(row)
          .filter(([, value]) => value !== undefined && value !== null && String(value).trim())
          .map(([key, value]) => `${key}: ${String(value)}`)
          .join('\n');
      return {
        title,
        content,
        category: readNullableString(row, ['category', 'type', 'request_type']),
        source: readNullableString(row, ['source', 'url', 'file']),
      };
    })
    .filter((document) => document.title.trim() && document.content.trim());
}

function parseCsvProducts(text: string): Record<string, unknown>[] {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];

  const headers = rows[0].map((header) => header.trim()).filter(Boolean);
  if (headers.length === 0) return [];

  return rows
    .slice(1)
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row) => {
      const product: Record<string, unknown> = {};
      headers.forEach((header, index) => {
        const rawValue = row[index]?.trim() ?? '';
        product[header] = normalizeCsvValue(header, rawValue);
      });
      return product;
    });
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"' && inQuotes && next === '"') {
      cell += '"';
      i++;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === ',' && !inQuotes) {
      row.push(cell);
      cell = '';
      continue;
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
      continue;
    }

    cell += char;
  }

  row.push(cell);
  rows.push(row);

  return rows;
}

function normalizeCsvValue(header: string, value: string): unknown {
  if (!value) return '';
  if (header === 'price') {
    const numeric = Number(value.replace(/,/g, ''));
    return Number.isNaN(numeric) ? value : numeric;
  }
  if (header === 'features') {
    return value
      .split(/[|;]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return value;
}

function readProductTitle(product: ProductItem, index: number): string {
  const name = product['name'];
  return typeof name === 'string' && name.trim() ? name : `상품 ${index + 1}`;
}

function readProductMeta(product: ProductItem): string {
  const chunks: string[] = [];
  const category = product['category'];
  const price = product['price'];
  const target = product['target'];

  if (typeof category === 'string' && category.trim()) chunks.push(category);
  if (typeof price === 'number') chunks.push(`${price.toLocaleString()}원`);
  if (typeof price === 'string' && price.trim()) chunks.push(price);
  if (typeof target === 'string' && target.trim()) chunks.push(target);

  return chunks.length > 0 ? chunks.join(' · ') : '상품 정보';
}

function readProductFeatures(product: ProductItem): string {
  const features = product['features'];
  const painPoint = product['pain_point'];
  const chunks: string[] = [];

  if (Array.isArray(features)) {
    chunks.push(features.map(String).join(', '));
  } else if (typeof features === 'string' && features.trim()) {
    chunks.push(features);
  }
  if (typeof painPoint === 'string' && painPoint.trim()) {
    chunks.push(painPoint);
  }

  return chunks.length > 0 ? chunks.join(' / ') : '특징 정보 없음';
}

function readInquiryTitle(inquiry: CsInquiry, index: number): string {
  const id = inquiry['inquiry_id'];
  const type = inquiry['request_type'];
  const product = inquiry['product_name'];
  const fallback = `문의 ${index + 1}`;
  return [id, type, product]
    .filter((value) => typeof value === 'string' && value.trim())
    .join(' · ') || fallback;
}

function readInquiryMeta(inquiry: CsInquiry): string {
  const chunks = ['received_at', 'product_received_at', 'used', 'tag_removed']
    .map((field) => {
      const value = inquiry[field];
      return value === undefined || value === '' ? null : `${field}: ${String(value)}`;
    })
    .filter((value): value is string => value !== null);
  return chunks.length > 0 ? chunks.join(' · ') : '문의 정보';
}

function readInquiryMessage(inquiry: CsInquiry): string {
  const message = inquiry['customer_message'];
  return typeof message === 'string' && message.trim() ? message : '문의 내용 없음';
}

function buildOrderContext(inquiry: CsInquiry): Record<string, unknown> {
  const context: Record<string, unknown> = {};
  Object.entries(inquiry).forEach(([key, value]) => {
    if (key === 'customer_message' || value === undefined || value === null || value === '') return;
    context[key] = value;
  });
  return context;
}

function mapCsAnalyzeResponse(value: unknown, inquiry: CsInquiry, index: number): CsAnswerDraft {
  const record = asRecord(value) ?? {};
  const safetyReview = asRecord(record['safety_review']) ?? {};
  const matchedPolicies = Array.isArray(record['matched_policies'])
    ? record['matched_policies']
        .map((item) => asRecord(item))
        .filter((item): item is Record<string, unknown> => item !== null)
    : [];
  const missingInfo = Array.isArray(record['missing_info'])
    ? record['missing_info'].map(String).filter(Boolean)
    : [];
  const evidence = matchedPolicies
    .map((policy) => {
      const title = readString(policy, ['title']) ?? '정책';
      const source = readString(policy, ['source']);
      return source ? `${title} (${source})` : title;
    })
    .filter(Boolean);
  const decisionReason = readString(record, ['decision_reason']);

  return {
    inquiryTitle: readInquiryTitle(inquiry, index),
    requestType:
      readString(record, ['category_label', 'category']) ??
      readNullableString(inquiry, ['request_type', 'category', 'type']) ??
      '문의',
    decision: readString(record, ['decision_label', 'decision']) ?? '확인 필요',
    risk: readString(safetyReview, ['risk_level']) ?? 'unknown',
    evidence: evidence.length > 0 ? evidence : decisionReason ? [decisionReason] : [],
    missingFields: missingInfo,
    answer: readString(record, ['draft_reply', 'answer', 'reply']) ?? formatJson(value),
  };
}

async function postJson(url: string, payload: unknown): Promise<unknown> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const json = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    throw new Error(`Backend request failed (${response.status}): ${formatJson(json)}`);
  }
  return json;
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function normalizeThreadContent(value: string): string {
  return value.replace(/\r\n/g, '\n').trim();
}

function extractThreadContents(value: unknown): string[] {
  const contents: string[] = [];
  collectThreadContents(value, contents);
  return [...new Set(contents.map((item) => item.trim()).filter(Boolean))];
}

function collectThreadContents(value: unknown, contents: string[]): void {
  if (typeof value === 'string') return;

  if (Array.isArray(value)) {
    for (const item of value) {
      collectThreadContents(item, contents);
    }
    return;
  }

  const record = asRecord(value);
  if (!record) return;

  const direct = readString(record, [
    'content',
    'text',
    'draftText',
    'thread',
    'post',
    'caption',
    'generatedContent',
    'generatedText',
    'threadContent',
  ]);
  if (direct) {
    contents.push(direct);
  }

  for (const field of ['result', 'data', 'thread', 'post', 'draft', 'output', 'response']) {
    collectThreadContents(record[field], contents);
  }

  for (const field of ['contents', 'drafts', 'threads', 'posts', 'items', 'outputs', 'results']) {
    collectThreadContents(record[field], contents);
  }
}

function readString(record: Record<string, unknown>, fields: string[]): string | null {
  for (const field of fields) {
    const value = record[field];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return null;
}

function readNullableString(record: Record<string, unknown>, fields: string[]): string | null {
  return readString(record, fields);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}
