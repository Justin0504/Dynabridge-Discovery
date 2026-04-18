"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Upload,
  Globe,
  Plus,
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  Send,
  CheckCircle2,
  Loader2,
  Circle,
  FileText,
  MessageSquare,
  History,
  FolderOpen,
  Clock,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { t, type Locale } from "@/lib/i18n";
import {
  listProjects,
  createProject,
  getProject,
  uploadFile,
  generateReport,
  getSlides,
  addComment,
  getComments,
  downloadUrl,
  deleteProject,
  type Project,
  type SlidePreview,
  type Comment,
  type ProgressEvent,
} from "@/lib/api";

type Step = "scraping" | "ecommerce" | "parsing" | "reviews" | "competitors" | "analyzing" | "generating";

const STEPS: Step[] = ["scraping", "ecommerce", "parsing", "reviews", "competitors", "analyzing", "generating"];

type Phase = "brand_reality" | "market_structure" | "full";

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: "bg-neutral-100", text: "text-neutral-600" },
  scraping: { bg: "bg-yellow-50", text: "text-yellow-700" },
  parsing: { bg: "bg-yellow-50", text: "text-yellow-700" },
  analyzing: { bg: "bg-blue-50", text: "text-blue-700" },
  generating: { bg: "bg-blue-50", text: "text-blue-700" },
  review: { bg: "bg-orange-50", text: "text-orange-700" },
  approved: { bg: "bg-green-50", text: "text-green-700" },
};

const PHASE_COLORS: Record<string, { bg: string; text: string }> = {
  brand_reality: { bg: "bg-violet-50", text: "text-violet-700" },
  market_structure: { bg: "bg-cyan-50", text: "text-cyan-700" },
  full: { bg: "bg-amber-50", text: "text-amber-700" },
};

function formatDate(iso: string, locale: Locale): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return locale === "zh" ? "刚刚" : "just now";
  if (diffMin < 60) return locale === "zh" ? `${diffMin}分钟前` : `${diffMin}m ago`;
  if (diffHr < 24) return locale === "zh" ? `${diffHr}小时前` : `${diffHr}h ago`;
  if (diffDay < 7) return locale === "zh" ? `${diffDay}天前` : `${diffDay}d ago`;
  return d.toLocaleDateString(locale === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function Home() {
  const [locale, setLocale] = useState<Locale>("en");

  // History panel state
  const [historyOpen, setHistoryOpen] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);

  // Form state
  const [projectName, setProjectName] = useState("");
  const [brandUrl, setBrandUrl] = useState("");
  const [competitors, setCompetitors] = useState<string[]>([]);
  const [competitorInput, setCompetitorInput] = useState("");
  const [language, setLanguage] = useState("en");
  const [phase, setPhase] = useState<Phase>("brand_reality");
  const [files, setFiles] = useState<File[]>([]);

  // Pipeline state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState<Step | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<Step>>(new Set());
  const [projectId, setProjectId] = useState<number | null>(null);

  // Preview state
  const [slides, setSlides] = useState<SlidePreview[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);

  // Discovered competitors state
  const [discoveredCompetitors, setDiscoveredCompetitors] = useState<
    { name: string; source: string; confidence: number; category_role?: string; reason?: string }[]
  >([]);

  // Review state
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentText, setCommentText] = useState("");
  const [authorName, setAuthorName] = useState("");

  // Toast notifications
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" } | null>(null);
  const showToast = (message: string, type: "error" | "success" = "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoadingProjects(true);
      const data = await listProjects();
      setProjects(data);
    } catch {
      showToast("Failed to load projects");
    } finally {
      setLoadingProjects(false);
    }
  };

  const handleLoadProject = async (project: Project) => {
    setActiveProjectId(project.id);
    setProjectId(project.id);
    setProjectName(project.name);
    setBrandUrl(project.brand_url);
    setCompetitors(project.competitor_urls || []);
    setLanguage(project.language);
    setPhase((project.phase || "brand_reality") as Phase);
    setFiles([]);
    setDiscoveredCompetitors([]);
    setCompletedSteps(new Set());
    setCurrentStep(null);
    setIsGenerating(false);

    // Load slides if available
    try {
      const slideData = await getSlides(project.id);
      setSlides(slideData);
      setCurrentSlide(0);
    } catch {
      setSlides([]);
    }

    // Load comments
    try {
      const commentData = await getComments(project.id);
      setComments(commentData);
    } catch {
      setComments([]);
    }
  };

  const handleNewProject = () => {
    setActiveProjectId(null);
    setProjectId(null);
    setProjectName("");
    setBrandUrl("");
    setCompetitors([]);
    setCompetitorInput("");
    setLanguage("en");
    setPhase("brand_reality");
    setFiles([]);
    setSlides([]);
    setComments([]);
    setDiscoveredCompetitors([]);
    setCompletedSteps(new Set());
    setCurrentStep(null);
    setIsGenerating(false);
  };

  const handleDeleteProject = async (pid: number) => {
    try {
      await deleteProject(pid);
      if (activeProjectId === pid) handleNewProject();
      loadProjects();
      showToast("Project deleted", "success");
    } catch {
      showToast("Failed to delete project");
    }
  };

  const handleAddCompetitor = () => {
    if (competitorInput.trim()) {
      setCompetitors((prev) => [...prev, competitorInput.trim()]);
      setCompetitorInput("");
    }
  };

  const handleRemoveCompetitor = (index: number) => {
    setCompetitors((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
    }
  }, []);

  const handleGenerate = async () => {
    if (!projectName.trim()) return;

    setIsGenerating(true);
    setCompletedSteps(new Set());
    setCurrentStep(null);
    setSlides([]);

    try {
      // Create or reuse project
      let pid = projectId;
      if (!pid) {
        const project = await createProject({
          name: projectName,
          brand_url: brandUrl,
          competitor_urls: competitors,
          language,
          phase,
        });
        pid = project.id;
        setProjectId(pid);
        setActiveProjectId(pid);
      }

      // Upload files
      for (const file of files) {
        await uploadFile(pid, file);
      }

      // Generate report with SSE progress
      setDiscoveredCompetitors([]);
      generateReport(
        pid,
        (event: ProgressEvent & { competitors?: typeof discoveredCompetitors }) => {
          setCurrentStep(event.step as Step);
          if (event.done) {
            setCompletedSteps((prev) => new Set([...prev, event.step as Step]));
          }
          // Capture discovered competitors
          if (event.step === "competitors" && event.competitors) {
            setDiscoveredCompetitors(event.competitors);
            // Also update the competitor chips in the form
            const names = event.competitors.map((c: { name: string }) => c.name);
            setCompetitors((prev) => {
              const existing = new Set(prev.map((p) => p.toLowerCase()));
              const merged = [...prev];
              for (const name of names) {
                if (!existing.has(name.toLowerCase())) {
                  merged.push(name);
                }
              }
              return merged;
            });
          }
        },
        async () => {
          setIsGenerating(false);
          setCurrentStep(null);
          showToast("Report generated successfully!", "success");
          // Load slide previews
          const slideData = await getSlides(pid!);
          setSlides(slideData);
          setCurrentSlide(0);
          // Load comments
          const commentData = await getComments(pid!);
          setComments(commentData);
          // Refresh project list
          loadProjects();
        },
        (msg: string) => {
          setIsGenerating(false);
          showToast(msg || "Generation failed");
          loadProjects();
        },
        phase
      );
    } catch (err) {
      setIsGenerating(false);
      showToast("Failed to start generation");
    }
  };

  const handleSubmitComment = async () => {
    if (!commentText.trim() || !authorName.trim() || projectId === null) return;
    const comment = await addComment(projectId, {
      slide_order: currentSlide,
      author: authorName,
      content: commentText,
    });
    setComments((prev) => [...prev, comment]);
    setCommentText("");
  };

  const slideComments = comments.filter(
    (c) => c.slide_order === currentSlide || c.slide_order === null
  );

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center justify-between px-6 h-14 border-b border-neutral-200 bg-white">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors text-neutral-500"
            title={historyOpen ? "Hide history" : "Show history"}
          >
            {historyOpen ? (
              <PanelLeftClose className="w-5 h-5" />
            ) : (
              <PanelLeftOpen className="w-5 h-5" />
            )}
          </button>
          <img src="/logo.png" alt="DynaBridge" className="h-9 object-contain" />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLocale(locale === "en" ? "zh" : "en")}
            className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-brand-500 rounded-lg hover:bg-brand-50 transition-colors"
          >
            {locale === "en" ? "中文" : "EN"}
          </button>
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* History Sidebar */}
        {historyOpen && (
          <aside className="w-[260px] border-r border-neutral-200 bg-neutral-50 flex flex-col overflow-hidden">
            {/* History header */}
            <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-neutral-500" />
                <span className="text-sm font-medium text-neutral-700">
                  {t("history.title", locale)}
                </span>
              </div>
              <button
                onClick={handleNewProject}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors"
              >
                <Plus className="w-3 h-3" />
                {t("history.new", locale)}
              </button>
            </div>

            {/* Project list */}
            <div className="flex-1 overflow-y-auto">
              {loadingProjects ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
                </div>
              ) : projects.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-neutral-400">
                  <FolderOpen className="w-8 h-8 mb-2" />
                  <p className="text-sm">{t("history.empty", locale)}</p>
                </div>
              ) : (
                <div className="py-1">
                  {projects.map((p) => {
                    const isActive = activeProjectId === p.id;
                    const sc = STATUS_COLORS[p.status] || STATUS_COLORS.draft;
                    const pc = PHASE_COLORS[p.phase] || PHASE_COLORS.brand_reality;
                    return (
                      <button
                        key={p.id}
                        onClick={() => handleLoadProject(p)}
                        className={`w-full text-left px-4 py-3 border-b border-neutral-100 hover:bg-white transition-colors ${
                          isActive ? "bg-white border-l-2 border-l-brand-500" : ""
                        }`}
                      >
                        {/* Project name */}
                        <div className="flex items-start justify-between gap-2">
                          <span className={`text-sm font-medium truncate ${isActive ? "text-brand-600" : "text-neutral-800"}`}>
                            {p.name}
                          </span>
                          <span
                            role="button"
                            onClick={(e) => { e.stopPropagation(); handleDeleteProject(p.id); }}
                            className="text-neutral-300 hover:text-red-500 shrink-0 p-0.5"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </span>
                        </div>

                        {/* Status + Phase badges */}
                        <div className="flex items-center gap-1.5 mt-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${sc.bg} ${sc.text}`}>
                            {t(`project.status.${p.status}`, locale)}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${pc.bg} ${pc.text}`}>
                            {t(`history.phase.${p.phase || "brand_reality"}`, locale)}
                          </span>
                        </div>

                        {/* Meta row */}
                        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-neutral-400">
                          <span className="flex items-center gap-0.5">
                            <Clock className="w-3 h-3" />
                            {formatDate(p.updated_at || p.created_at, locale)}
                          </span>
                          {p.slide_count > 0 && (
                            <span className="flex items-center gap-0.5">
                              <Layers className="w-3 h-3" />
                              {p.slide_count} {t("history.slides", locale)}
                            </span>
                          )}
                          {p.comment_count > 0 && (
                            <span className="flex items-center gap-0.5">
                              <MessageSquare className="w-3 h-3" />
                              {p.comment_count}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Left Panel — Input & Controls */}
        <aside className="w-[380px] border-r border-neutral-200 bg-white flex flex-col overflow-y-auto">
          <div className="p-5 space-y-5">
            {/* Project Name */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.name", locale)}
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder={t("form.name.placeholder", locale)}
                className="w-full px-3 py-2 border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
              />
            </div>

            {/* Brand URL */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.url", locale)}
              </label>
              <div className="relative">
                <Globe className="absolute left-3 top-2.5 w-4 h-4 text-neutral-400" />
                <input
                  type="url"
                  value={brandUrl}
                  onChange={(e) => setBrandUrl(e.target.value)}
                  placeholder={t("form.url.placeholder", locale)}
                  className="w-full pl-9 pr-3 py-2 border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
                />
              </div>
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.files", locale)}
              </label>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-neutral-200 rounded-xl p-4 text-center cursor-pointer hover:border-brand-300 hover:bg-brand-50/30 transition-all"
              >
                <Upload className="w-6 h-6 text-neutral-400 mx-auto mb-2" />
                <p className="text-sm text-neutral-500">
                  {t("form.files.hint", locale)}
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.doc,.pptx,.png,.jpg,.jpeg"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
              {files.length > 0 && (
                <div className="mt-2 space-y-1">
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-3 py-1.5 bg-neutral-50 rounded-lg text-sm"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-4 h-4 text-brand-500 shrink-0" />
                        <span className="truncate">{f.name}</span>
                      </div>
                      <button
                        onClick={() => handleRemoveFile(i)}
                        className="text-neutral-400 hover:text-red-500 shrink-0"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Competitors */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.competitors", locale)}
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={competitorInput}
                  onChange={(e) => setCompetitorInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddCompetitor()}
                  placeholder={t("form.competitors.placeholder", locale)}
                  className="flex-1 px-3 py-2 border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
                />
                <button
                  onClick={handleAddCompetitor}
                  className="px-3 py-2 bg-neutral-100 hover:bg-neutral-200 rounded-xl transition-colors"
                >
                  <Plus className="w-4 h-4 text-neutral-600" />
                </button>
              </div>
              {competitors.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {competitors.map((c, i) => {
                    const disc = discoveredCompetitors.find(
                      (d) => d.name.toLowerCase() === c.toLowerCase()
                    );
                    return (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-50 text-brand-700 rounded-lg text-sm"
                      >
                        {c}
                        {disc && (
                          <span
                            className={`text-[9px] px-1 py-0.5 rounded font-medium ${
                              disc.source === "both"
                                ? "bg-green-100 text-green-700"
                                : disc.source === "amazon"
                                  ? "bg-orange-100 text-orange-700"
                                  : "bg-blue-100 text-blue-700"
                            }`}
                            title={disc.reason || disc.source}
                          >
                            {disc.source === "both" ? "AI+AMZ" : disc.source === "amazon" ? "AMZ" : "AI"}
                          </span>
                        )}
                        <button
                          onClick={() => handleRemoveCompetitor(i)}
                          className="hover:text-red-500"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
              {discoveredCompetitors.length > 0 && (
                <p className="mt-1.5 text-[11px] text-neutral-400">
                  {locale === "zh"
                    ? `已自动发现 ${discoveredCompetitors.length} 个竞品（AI + Amazon）`
                    : `${discoveredCompetitors.length} competitors auto-discovered (AI + Amazon)`}
                </p>
              )}
            </div>

            {/* Language */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.language", locale)}
              </label>
              <div className="flex gap-2">
                {[
                  { value: "en", label: t("form.language.en", locale) },
                  { value: "zh", label: t("form.language.zh", locale) },
                  { value: "en+zh", label: t("form.language.both", locale) },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setLanguage(opt.value)}
                    className={`flex-1 py-2 text-sm rounded-xl transition-all ${
                      language === opt.value
                        ? "bg-brand-500 text-white shadow-sm"
                        : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Phase */}
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                {t("form.phase", locale)}
              </label>
              <div className="flex gap-2">
                {([
                  { value: "brand_reality", label: t("form.phase.brand_reality", locale) },
                  { value: "market_structure", label: t("form.phase.market_structure", locale) },
                  { value: "full", label: t("form.phase.full", locale) },
                ] as const).map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setPhase(opt.value)}
                    className={`flex-1 py-2 text-sm rounded-xl transition-all ${
                      phase === opt.value
                        ? "bg-brand-500 text-white shadow-sm"
                        : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-xs text-neutral-400">
                {phase === "brand_reality"
                  ? locale === "zh" ? "仅生成品牌能力分析（第一期交付）" : "Capabilities analysis only (Phase 1 delivery)"
                  : phase === "market_structure"
                    ? locale === "zh" ? "品牌能力 + 竞争格局分析" : "Capabilities + Competition analysis"
                    : locale === "zh" ? "完整品牌发现报告（含消费者洞察）" : "Full Brand Discovery report (incl. Consumer insights)"}
              </p>
            </div>

            {/* Divider */}
            <div className="border-t border-neutral-100" />

            {/* Progress */}
            {(isGenerating || completedSteps.size > 0) && (
              <div className="space-y-2.5">
                {STEPS.map((step) => {
                  const isDone = completedSteps.has(step);
                  const isCurrent = currentStep === step;
                  return (
                    <div key={step} className="flex items-center gap-2.5">
                      {isDone ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                      ) : isCurrent ? (
                        <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
                      ) : (
                        <Circle className="w-5 h-5 text-neutral-300" />
                      )}
                      <span
                        className={`text-sm ${
                          isDone
                            ? "text-green-600"
                            : isCurrent
                              ? "text-brand-500 font-medium"
                              : "text-neutral-400"
                        }`}
                      >
                        {t(`progress.${step}`, locale)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !projectName.trim()}
              className="w-full py-3 bg-brand-500 text-white font-medium rounded-xl hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t("form.generating", locale)}
                </>
              ) : (
                t("form.generate", locale)
              )}
            </button>

            {/* Download + Regenerate */}
            {projectId && slides.length > 0 && (
              <div className="flex gap-2">
                <a
                  href={downloadUrl(projectId)}
                  className="flex-1 py-2.5 flex items-center justify-center gap-2 border border-brand-500 text-brand-500 font-medium rounded-xl hover:bg-brand-50 transition-all text-sm"
                >
                  <Download className="w-4 h-4" />
                  {t("download.pptx", locale)}
                </a>
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="py-2.5 px-4 flex items-center justify-center gap-2 border border-neutral-300 text-neutral-600 font-medium rounded-xl hover:bg-neutral-50 disabled:opacity-50 transition-all text-sm"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* Right Panel — Preview & Review */}
        <main className="flex-1 flex flex-col bg-neutral-50 overflow-hidden">
          {slides.length === 0 ? (
            /* Empty state */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-10 h-10 text-brand-300" />
                </div>
                <p className="text-neutral-400 text-lg">
                  {t("preview.empty", locale)}
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Slide Preview Area */}
              <div className="flex-1 flex items-center justify-center p-6 min-h-0">
                <div className="relative w-full max-w-4xl aspect-[16/9]">
                  {/* Slide image */}
                  <div className="w-full h-full bg-white rounded-xl shadow-lg overflow-hidden border border-neutral-200">
                    {slides[currentSlide]?.preview_url ? (
                      <img
                        src={slides[currentSlide].preview_url}
                        alt={`Slide ${currentSlide + 1}`}
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-neutral-400">
                        {t("preview.slide", locale)} {currentSlide + 1}
                      </div>
                    )}
                  </div>

                  {/* Navigation arrows */}
                  <button
                    onClick={() => setCurrentSlide((s) => Math.max(0, s - 1))}
                    disabled={currentSlide === 0}
                    className="absolute left-[-48px] top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-white shadow-md hover:bg-neutral-50 disabled:opacity-30 transition-all"
                  >
                    <ChevronLeft className="w-5 h-5 text-neutral-600" />
                  </button>
                  <button
                    onClick={() =>
                      setCurrentSlide((s) =>
                        Math.min(slides.length - 1, s + 1)
                      )
                    }
                    disabled={currentSlide === slides.length - 1}
                    className="absolute right-[-48px] top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-white shadow-md hover:bg-neutral-50 disabled:opacity-30 transition-all"
                  >
                    <ChevronRight className="w-5 h-5 text-neutral-600" />
                  </button>
                </div>
              </div>

              {/* Slide counter + slide strip */}
              <div className="px-6 pb-2">
                <div className="flex items-center justify-center gap-2 text-sm text-neutral-500 mb-3">
                  <span>
                    {t("preview.slide", locale)} {currentSlide + 1}{" "}
                    {t("preview.of", locale)} {slides.length}
                  </span>
                </div>
                <div className="flex gap-1.5 overflow-x-auto pb-2 justify-center">
                  {slides.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setCurrentSlide(i)}
                      className={`w-16 h-10 rounded-md border-2 transition-all shrink-0 flex items-center justify-center text-xs ${
                        i === currentSlide
                          ? "border-brand-500 bg-brand-50 text-brand-500 font-medium"
                          : "border-neutral-200 bg-white text-neutral-400 hover:border-neutral-300"
                      }`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              </div>

              {/* Comment section */}
              <div className="border-t border-neutral-200 bg-white px-6 py-4">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-4 h-4 text-brand-500" />
                  <h3 className="text-sm font-medium text-neutral-700">
                    {t("review.title", locale)}
                  </h3>
                  {slideComments.length > 0 && (
                    <span className="text-xs bg-brand-50 text-brand-500 px-2 py-0.5 rounded-full">
                      {slideComments.length}
                    </span>
                  )}
                </div>

                {/* Existing comments */}
                {slideComments.length > 0 && (
                  <div className="space-y-2 mb-3 max-h-32 overflow-y-auto">
                    {slideComments.map((c) => (
                      <div
                        key={c.id}
                        className={`flex items-start gap-2 px-3 py-2 rounded-lg text-sm ${
                          c.resolved
                            ? "bg-green-50 text-green-700"
                            : "bg-neutral-50 text-neutral-700"
                        }`}
                      >
                        <span className="font-medium shrink-0">
                          {c.author}:
                        </span>
                        <span className="flex-1">{c.content}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* New comment input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={authorName}
                    onChange={(e) => setAuthorName(e.target.value)}
                    placeholder={t("review.author", locale)}
                    className="w-24 px-3 py-2 border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                  />
                  <input
                    type="text"
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSubmitComment()}
                    placeholder={t("review.placeholder", locale)}
                    className="flex-1 px-3 py-2 border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                  />
                  <button
                    onClick={handleSubmitComment}
                    disabled={!commentText.trim() || !authorName.trim()}
                    className="px-4 py-2 bg-brand-500 text-white rounded-xl hover:bg-brand-600 disabled:opacity-50 transition-all"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </>
          )}
        </main>
      </div>

      {/* Toast notification */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium transition-all ${
          toast.type === "error"
            ? "bg-red-600 text-white"
            : "bg-green-600 text-white"
        }`}>
          {toast.message}
          <button onClick={() => setToast(null)} className="ml-3 opacity-70 hover:opacity-100">
            <X className="w-3.5 h-3.5 inline" />
          </button>
        </div>
      )}
    </div>
  );
}
