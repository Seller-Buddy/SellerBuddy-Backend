import { useCallback, useEffect, useRef, useState } from 'react';

import { toMajorMinor } from './changelogData.js';
import { AgentCommandPanel } from './components/AgentCommandPanel.js';
import { BottomToolbar } from './components/BottomToolbar.js';
import { ChangelogModal } from './components/ChangelogModal.js';
import { DebugView } from './components/DebugView.js';
import { EditActionBar } from './components/EditActionBar.js';
import { MigrationNotice } from './components/MigrationNotice.js';
import { SettingsModal } from './components/SettingsModal.js';
import { Tooltip } from './components/Tooltip.js';
import { Button } from './components/ui/Button.js';
import { Modal } from './components/ui/Modal.js';
import { VersionIndicator } from './components/VersionIndicator.js';
import { ZoomControls } from './components/ZoomControls.js';
import { useEditorActions } from './hooks/useEditorActions.js';
import { useEditorKeyboard } from './hooks/useEditorKeyboard.js';
import { useExtensionMessages } from './hooks/useExtensionMessages.js';
import { OfficeCanvas } from './office/components/OfficeCanvas.js';
import { ToolOverlay } from './office/components/ToolOverlay.js';
import { EditorState } from './office/editor/editorState.js';
import { EditorToolbar } from './office/editor/EditorToolbar.js';
import { OfficeState } from './office/engine/officeState.js';
import { isRotatable } from './office/layout/furnitureCatalog.js';
import { getPetCount } from './office/sprites/petSpriteData.js';
import { EditTool } from './office/types.js';
import { isBrowserRuntime, isE2E } from './runtime.js';
import { installTestHooks } from './testHooks.js';
import { transport } from './transport/index.js';

// Game state lives outside React — updated imperatively by message handlers
const officeStateRef = { current: null as OfficeState | null };
const editorState = new EditorState();

const SELLER_AGENTS = [
  {
    id: 100,
    department: 'marketing',
    name: 'ProductCatalogAgent',
    shortName: 'Catalog',
    status: 'Managing product list',
    responsibilities: ['상품 리스트 업로드 확인하기', '선택 상품 전달하기'],
  },
  {
    id: 101,
    department: 'marketing',
    name: 'ProductParserAgent',
    shortName: 'Parser',
    status: 'Normalizing product JSON',
    responsibilities: ['JSON 입력 받기', '상품 정보 정규화하기'],
  },
  {
    id: 102,
    department: 'marketing',
    name: 'ProductInsightAgent',
    shortName: 'Insight',
    status: 'Extracting customer insights',
    responsibilities: ['소구 포인트 추출하기', '타겟 고객과 페인포인트 정리하기'],
  },
  {
    id: 103,
    department: 'marketing',
    name: 'ThreadWriterAgent',
    shortName: 'Writer',
    status: 'Drafting Threads candidates',
    responsibilities: ['Threads 게시글 후보 생성하기'],
  },
  {
    id: 104,
    department: 'marketing',
    name: 'ContentReviewAgent',
    shortName: 'Review',
    status: 'Reviewing content quality',
    responsibilities: ['글자수 확인하기', '과장 표현 확인하기', '상품 정보 불일치 확인하기'],
  },
  {
    id: 110,
    department: 'cs',
    name: 'InquiryIntakeAgent',
    shortName: 'Intake',
    status: 'Reading CS inquiries',
    responsibilities: ['문의 CSV 접수하기', '주문번호, 상품명, 고객 메시지 정리하기'],
  },
  {
    id: 111,
    department: 'cs',
    name: 'InquiryClassifierAgent',
    shortName: 'Classify',
    status: 'Classifying inquiry type',
    responsibilities: ['반품, 교환, 배송, 환불, 불량 유형 분류하기'],
  },
  {
    id: 112,
    department: 'cs',
    name: 'InfoCheckAgent',
    shortName: 'InfoCheck',
    status: 'Checking required fields',
    responsibilities: ['수령일, 사용 여부, 택 제거 여부 확인하기', '누락 정보 표시하기'],
  },
  {
    id: 113,
    department: 'cs',
    name: 'PolicySearchAgent',
    shortName: 'Policy',
    status: 'Finding matching policies',
    responsibilities: ['정책 CSV 검색하기', '상품명과 문의 유형에 맞는 정책 찾기'],
  },
  {
    id: 114,
    department: 'cs',
    name: 'DecisionAgent',
    shortName: 'Decision',
    status: 'Preparing policy decision',
    responsibilities: ['가능, 불가, 추가 확인 필요 판단하기'],
  },
  {
    id: 115,
    department: 'cs',
    name: 'ReplyWriterAgent',
    shortName: 'Reply',
    status: 'Waiting for backend reply API',
    responsibilities: ['백엔드 답변 생성 결과 받기', '고객 답변 초안 표시하기'],
  },
  {
    id: 116,
    department: 'cs',
    name: 'SafetyReviewAgent',
    shortName: 'Safety',
    status: 'Reviewing response risk',
    responsibilities: ['과도한 확정 표현 검수하기', '환불, 보상 오안내 확인하기'],
  },
] as const;

function getSellerAgentTeamName(agent: (typeof SELLER_AGENTS)[number]): string {
  return agent.department === 'cs' ? 'CS Automation' : 'Marketing';
}

function getSellerAgentNameClass(agent: (typeof SELLER_AGENTS)[number]): string {
  return agent.department === 'cs' ? 'text-status-success' : 'text-accent-bright';
}
// Test-only observability hooks (message/sound logs, addAgent wrapper, selectAgent).
// Installed only under the e2e harness so they never patch prototypes or grow
// unbounded logs in a real user's session.
if (isE2E) installTestHooks(officeStateRef);

function getOfficeState(): OfficeState {
  if (!officeStateRef.current) {
    officeStateRef.current = new OfficeState();
  }
  return officeStateRef.current;
}

function App() {
  const [selectedSellerAgentId, setSelectedSellerAgentId] = useState<number | null>(null);
  const [sellerAgentDialogues, setSellerAgentDialogues] = useState<Record<number, string>>({});

  // Browser runtime (dev or static dist): dispatch mock messages after the
  // useExtensionMessages listener has been registered.
  useEffect(() => {
    // browserMock is for Vite dev mode only (UI prototyping without a server).
    // In standalone server mode, the server sends all state over WebSocket.
    // In VS Code mode, the extension sends all state via postMessage.
    if (isBrowserRuntime && import.meta.env.DEV) {
      void import('./browserMock.js').then(({ dispatchMockMessages }) => dispatchMockMessages());
    }
  }, []);

  const editor = useEditorActions(getOfficeState, editorState);

  const isEditDirty = useCallback(
    () => editor.isEditMode && editor.isDirty,
    [editor.isEditMode, editor.isDirty],
  );

  const {
    agents,
    selectedAgent,
    agentTools,
    agentStatuses,
    subagentTools,
    subagentCharacters,
    layoutReady,
    layoutWasReset,
    loadedAssets,
    workspaceFolders,
    externalAssetDirectories,
    lastSeenVersion,
    extensionVersion,
    watchAllSessions,
    setWatchAllSessions,
    alwaysShowLabels,
    hooksEnabled,
    setHooksEnabled,
    hooksInfoShown,
  } = useExtensionMessages(getOfficeState, editor.setLastSavedLayout, isEditDirty);

  // Show migration notice once layout reset is detected
  const [migrationNoticeDismissed, setMigrationNoticeDismissed] = useState(false);
  const showMigrationNotice = layoutWasReset && !migrationNoticeDismissed;

  const [isChangelogOpen, setIsChangelogOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHooksInfoOpen, setIsHooksInfoOpen] = useState(false);
  const [hooksTooltipDismissed, setHooksTooltipDismissed] = useState(false);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [alwaysShowOverlay, setAlwaysShowOverlay] = useState(false);

  const currentMajorMinor = toMajorMinor(extensionVersion);

  const handleWhatsNewDismiss = useCallback(() => {
    transport.send({ type: 'setLastSeenVersion', version: currentMajorMinor });
  }, [currentMajorMinor]);

  const handleOpenChangelog = useCallback(() => {
    setIsChangelogOpen(true);
    transport.send({ type: 'setLastSeenVersion', version: currentMajorMinor });
  }, [currentMajorMinor]);

  // Sync alwaysShowOverlay from persisted settings
  useEffect(() => {
    setAlwaysShowOverlay(alwaysShowLabels);
  }, [alwaysShowLabels]);

  const handleToggleDebugMode = useCallback(() => setIsDebugMode((prev) => !prev), []);
  const handleToggleAlwaysShowOverlay = useCallback(() => {
    setAlwaysShowOverlay((prev) => {
      const newVal = !prev;
      transport.send({ type: 'setAlwaysShowLabels', enabled: newVal });
      return newVal;
    });
  }, []);

  const handleSelectAgent = useCallback((id: number) => {
    transport.send({ type: 'focusAgent', id });
  }, []);

  const containerRef = useRef<HTMLDivElement>(null);

  const [editorTickForKeyboard, setEditorTickForKeyboard] = useState(0);
  useEditorKeyboard(
    editor.isEditMode,
    editorState,
    editor.handleDeleteSelected,
    editor.handleRotateSelected,
    editor.handleToggleState,
    editor.handleUndo,
    editor.handleRedo,
    useCallback(() => setEditorTickForKeyboard((n) => n + 1), []),
    editor.handleToggleEditMode,
  );

  const handleCloseAgent = useCallback((id: number) => {
    transport.send({ type: 'closeAgent', id });
  }, []);

  const handleClick = useCallback((agentId: number) => {
    const sellerAgent = SELLER_AGENTS.find((agent) => agent.id === agentId);
    setSelectedSellerAgentId(sellerAgent ? agentId : null);

    // If clicked agent is a sub-agent, focus the parent's terminal instead
    const os = getOfficeState();
    const meta = os.subagentMeta.get(agentId);
    const focusId = meta ? meta.parentAgentId : agentId;
    transport.send({ type: 'focusAgent', id: focusId });
  }, []);

  const handleSellerAgentDialogue = useCallback((agentId: number, message: string) => {
    setSellerAgentDialogues((prev) => ({ ...prev, [agentId]: message }));
    window.setTimeout(() => {
      setSellerAgentDialogues((prev) => {
        if (prev[agentId] !== message) return prev;
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
    }, 4200);
  }, []);

  const officeState = getOfficeState();

  useEffect(() => {
    if (!layoutReady) return;

    for (const [index, agent] of SELLER_AGENTS.entries()) {
      const isDepartmentLead =
        SELLER_AGENTS.find((candidate) => candidate.department === agent.department)?.id ===
        agent.id;
      officeState.addAgent(agent.id, index, 0, undefined, true, agent.shortName);
      officeState.setTeamInfo(
        agent.id,
        getSellerAgentTeamName(agent),
        agent.name,
        isDepartmentLead,
        undefined,
        false,
      );
      officeState.setAgentTool(agent.id, agent.status);
      officeState.setAgentActive(agent.id, true);
    }
  }, [layoutReady, officeState]);

  const sellerAgentIds = SELLER_AGENTS.map((agent) => agent.id);
  const selectedSellerAgent =
    selectedSellerAgentId === null
      ? null
      : (SELLER_AGENTS.find((agent) => agent.id === selectedSellerAgentId) ?? null);
  const sellerAgentTools = SELLER_AGENTS.reduce<Record<number, { toolId: string; status: string; done: boolean }[]>>(
    (acc, agent) => {
      acc[agent.id] = [{ toolId: `seller-${agent.id}`, status: agent.status, done: false }];
      return acc;
    },
    {},
  );
  const sellerAgentDepartments = SELLER_AGENTS.reduce<Record<number, 'marketing' | 'cs'>>(
    (acc, agent) => {
      acc[agent.id] = agent.department;
      return acc;
    },
    {},
  );

  // Force dependency on editorTickForKeyboard to propagate keyboard-triggered re-renders
  void editorTickForKeyboard;

  // Show "Press R to rotate" hint when a rotatable item is selected or being placed
  const showRotateHint =
    editor.isEditMode &&
    (() => {
      if (editorState.selectedFurnitureUid) {
        const item = officeState
          .getLayout()
          .furniture.find((f) => f.uid === editorState.selectedFurnitureUid);
        if (item && isRotatable(item.type)) return true;
      }
      if (
        editorState.activeTool === EditTool.FURNITURE_PLACE &&
        isRotatable(editorState.selectedFurnitureType)
      ) {
        return true;
      }
      return false;
    })();

  if (!layoutReady) {
    return <div className="w-full h-full flex items-center justify-center ">Loading...</div>;
  }

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden">
      <OfficeCanvas
        officeState={officeState}
        onClick={handleClick}
        isEditMode={editor.isEditMode}
        editorState={editorState}
        onEditorTileAction={editor.handleEditorTileAction}
        onEditorEraseAction={editor.handleEditorEraseAction}
        onEditorSelectionChange={editor.handleEditorSelectionChange}
        onDeleteSelected={editor.handleDeleteSelected}
        onRotateSelected={editor.handleRotateSelected}
        onDragMove={editor.handleDragMove}
        editorTick={editor.editorTick}
        zoom={editor.zoom}
        onZoomChange={editor.handleZoomChange}
        panRef={editor.panRef}
      />

      {!isDebugMode ? (
        <>
          <ZoomControls zoom={editor.zoom} onZoomChange={editor.handleZoomChange} />

          {/* Vignette overlay */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{ background: 'var(--vignette)' }}
          />

          {editor.isEditMode && editor.isDirty && (
            <EditActionBar editor={editor} editorState={editorState} />
          )}

          {showRotateHint && (
            <div
              className="absolute left-1/2 -translate-x-1/2 z-11 bg-accent-bright text-white text-sm py-3 px-8 rounded-none border-2 border-accent shadow-pixel pointer-events-none whitespace-nowrap"
              style={{ top: editor.isDirty ? 64 : 8 }}
            >
              Rotate (R)
            </div>
          )}

          {editor.isEditMode &&
            (() => {
              const selUid = editorState.selectedFurnitureUid;
              const selColor = selUid
                ? (officeState.getLayout().furniture.find((f) => f.uid === selUid)?.color ?? null)
                : null;
              return (
                <EditorToolbar
                  activeTool={editorState.activeTool}
                  selectedTileType={editorState.selectedTileType}
                  selectedFurnitureType={editorState.selectedFurnitureType}
                  selectedFurnitureUid={selUid}
                  selectedFurnitureColor={selColor}
                  floorColor={editorState.floorColor}
                  wallColor={editorState.wallColor}
                  selectedWallSet={editorState.selectedWallSet}
                  onToolChange={editor.handleToolChange}
                  onTileTypeChange={editor.handleTileTypeChange}
                  onFloorColorChange={editor.handleFloorColorChange}
                  onWallColorChange={editor.handleWallColorChange}
                  onWallSetChange={editor.handleWallSetChange}
                  onSelectedFurnitureColorChange={editor.handleSelectedFurnitureColorChange}
                  onFurnitureTypeChange={editor.handleFurnitureTypeChange}
                  loadedAssets={loadedAssets}
                  activePetTypes={officeState.getActivePetTypes()}
                  petCount={getPetCount()}
                  onPetToggle={editor.handlePetToggle}
                />
              );
            })()}

          <ToolOverlay
            officeState={officeState}
            agents={[...sellerAgentIds, ...agents]}
            agentTools={{ ...sellerAgentTools, ...agentTools }}
            subagentCharacters={subagentCharacters}
            containerRef={containerRef}
            zoom={editor.zoom}
            panRef={editor.panRef}
            onCloseAgent={handleCloseAgent}
            alwaysShowOverlay={alwaysShowOverlay || sellerAgentIds.length > 0}
            agentDialogues={sellerAgentDialogues}
            agentDepartments={sellerAgentDepartments}
          />
          {selectedSellerAgent && (
            <SellerAgentDetailPanel
              agent={selectedSellerAgent}
              onClose={() => setSelectedSellerAgentId(null)}
            />
          )}
          <AgentCommandPanel onAgentDialogue={handleSellerAgentDialogue} />
        </>
      ) : (
        <DebugView
          agents={agents}
          selectedAgent={selectedAgent}
          agentTools={agentTools}
          agentStatuses={agentStatuses}
          subagentTools={subagentTools}
          officeState={officeState}
          onSelectAgent={handleSelectAgent}
        />
      )}

      {/* Hooks first-run tooltip */}
      {!hooksInfoShown && !hooksTooltipDismissed && (
        <Tooltip
          title="Instant Detection Active"
          position="top-right"
          onDismiss={() => {
            setHooksTooltipDismissed(true);
            transport.send({ type: 'setHooksInfoShown' });
          }}
        >
          <span className="text-sm text-text leading-none">
            Your agents now respond in real-time.{' '}
            <span
              className="text-accent cursor-pointer underline"
              onClick={() => {
                setIsHooksInfoOpen(true);
                setHooksTooltipDismissed(true);
                transport.send({ type: 'setHooksInfoShown' });
              }}
            >
              View more
            </span>
          </span>
        </Tooltip>
      )}

      {/* Hooks info modal */}
      <Modal
        isOpen={isHooksInfoOpen}
        onClose={() => setIsHooksInfoOpen(false)}
        title="Instant Detection is ON"
        zIndex={52}
      >
        <div className="text-base text-text px-10" style={{ lineHeight: 1.4 }}>
          <p className="mb-8">Your Pixel Agents office now reacts in real-time:</p>
          <ul className="mb-8 pl-18 list-disc m-0">
            <li className="text-sm mb-2">Permission prompts appear instantly</li>
            <li className="text-sm mb-2">Turn completions detected the moment they happen</li>
            <li className="text-sm mb-2">Sound notifications play immediately</li>
          </ul>
          <p className="mb-12 text-text-muted">
            This works through Claude Code Hooks, small event listeners that notify Pixel Agents
            whenever something happens in your Claude sessions.
          </p>
          <div className="text-center">
            <button
              onClick={() => setIsHooksInfoOpen(false)}
              className="py-4 px-20 text-lg bg-accent text-white border-2 border-accent rounded-none cursor-pointer shadow-pixel"
            >
              Got it
            </button>
          </div>
          <p className="mt-8 text-xs text-text-muted text-center">
            To disable, go to Settings {'>'} Instant Detection
          </p>
        </div>
      </Modal>

      <BottomToolbar
        isEditMode={editor.isEditMode}
        onOpenClaude={editor.handleOpenClaude}
        onToggleEditMode={editor.handleToggleEditMode}
        isSettingsOpen={isSettingsOpen}
        onToggleSettings={() => setIsSettingsOpen((v) => !v)}
        workspaceFolders={workspaceFolders}
      />

      <VersionIndicator
        currentVersion={extensionVersion}
        lastSeenVersion={lastSeenVersion}
        onDismiss={handleWhatsNewDismiss}
        onOpenChangelog={handleOpenChangelog}
      />

      <ChangelogModal
        isOpen={isChangelogOpen}
        onClose={() => setIsChangelogOpen(false)}
        currentVersion={extensionVersion}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        isDebugMode={isDebugMode}
        onToggleDebugMode={handleToggleDebugMode}
        alwaysShowOverlay={alwaysShowOverlay}
        onToggleAlwaysShowOverlay={handleToggleAlwaysShowOverlay}
        externalAssetDirectories={externalAssetDirectories}
        watchAllSessions={watchAllSessions}
        onToggleWatchAllSessions={() => {
          const newVal = !watchAllSessions;
          setWatchAllSessions(newVal);
          transport.send({ type: 'setWatchAllSessions', enabled: newVal });
        }}
        hooksEnabled={hooksEnabled}
        onToggleHooksEnabled={() => {
          const newVal = !hooksEnabled;
          setHooksEnabled(newVal);
          transport.send({ type: 'setHooksEnabled', enabled: newVal });
        }}
      />

      {showMigrationNotice && (
        <MigrationNotice onDismiss={() => setMigrationNoticeDismissed(true)} />
      )}
    </div>
  );
}

export default App;

interface SellerAgentDetailPanelProps {
  agent: (typeof SELLER_AGENTS)[number];
  onClose: () => void;
}

function SellerAgentDetailPanel({ agent, onClose }: SellerAgentDetailPanelProps) {
  return (
    <aside className="absolute top-24 left-10 z-30 w-300 pixel-panel p-8">
      <div className="flex items-start justify-between gap-8">
        <div className="min-w-0">
          <div className={`text-xs leading-none ${getSellerAgentNameClass(agent)}`}>
            {agent.name}
          </div>
          <div className="mt-4 text-[10px] text-text-muted leading-none">
            {getSellerAgentTeamName(agent)}
          </div>
          <div className="mt-5 text-[10px] text-text-muted leading-tight">{agent.status}</div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="shrink-0 px-4! py-1! text-[10px] leading-tight"
        >
          닫기
        </Button>
      </div>
      <div className="mt-8 flex flex-col gap-4">
        {agent.responsibilities.map((item) => (
          <div key={item} className="border border-border bg-bg-dark/70 p-5">
            <div className="text-[10px] text-text leading-tight">{item}</div>
          </div>
        ))}
      </div>
    </aside>
  );
}
