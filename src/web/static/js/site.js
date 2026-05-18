const SITE_LANG_KEY = "deeptrender.lang";

const SITE_I18N = {
  en: {
    "nav.overview": "Overview",
    "nav.domains": "Domains",
    "nav.topics": "Topics",
    "nav.venues": "Venues",
    "nav.explorer": "Explorer",
    "nav.arxiv": "arXiv",
    "nav.dataQuality": "Data Quality",
    "nav.home": "Home",
    "nav.trends": "Trend Tracking",
    "nav.compare": "Venue Comparison",
    "lang.en": "English",
    "lang.zh": "Chinese",

    "index.title": "DeepTrender - Structured AI/ML Paper Trend Database",
    "index.hero.kicker": "Topic data explorer",
    "index.hero.title": "DeepTrender",
    "index.hero.desc": "Structured AI/ML paper topics, evidence, relative_frequency, counts, and warnings.",
    "index.scope.label": "Source scope",
    "index.scope.preprint": "arXiv Preprint",
    "index.scope.accepted": "Conference Accepted",
    "index.scope.mixed": "Structured Mixed",
    "index.scope.note.preprint": "Current scope: arXiv Preprint. Preprints are not accepted conference evidence.",
    "index.scope.note.accepted": "Current scope: Conference Accepted. Evidence status remains labeled.",
    "index.scope.note.mixed": "Current scope: Structured Mixed. Accepted, preprint, mixed, and unknown evidence are labeled separately.",
    "index.stat.papers": "Structured Papers",
    "index.stat.keywords": "Tracked Keywords",
    "index.stat.venues": "Covered Venues",
    "index.stat.years": "Year Range",

    "index.quality.kicker": "Data Quality",
    "index.quality.title": "Visible warnings",
    "index.quality.loading": "Loading scoped quality checks...",
    "index.quality.empty": "No scoped warnings for the current quality report.",
    "index.quality.reportTitle": "Scoped Quality Report",
    "index.quality.reportDesc": "Metrics use the same warning thresholds as MCP tools.",
    "index.quality.sourceBreakdown": "Source Breakdown",

    "index.topics.kicker": "Canonical taxonomy",
    "index.topics.title": "Canonical Topics",
    "index.topics.desc": "Topic cards use normalized taxonomy entries. Counts remain visible; relative_frequency is primary where available.",
    "index.topics.use": "Use in explorer",
    "index.topics.queryScoped": "query-scoped",
    "index.topics.shownExplorer": "shown in explorer",

    "index.topicChart.title": "Topic Relative Frequency",
    "index.topicChart.subtitle": "Primary metric: relative_frequency. Count is shown alongside it.",

    "index.explorer.kicker": "Venue-Year-Topic Explorer",
    "index.explorer.title": "Inspect topic evidence",
    "index.explorer.desc": "Child topics are excluded by default.",
    "index.explorer.venue": "Venue",
    "index.explorer.year": "Year",
    "index.explorer.topic": "Topic query",
    "index.explorer.topicPlaceholder": "transformer, LLM, diffusion...",
    "index.explorer.includeChildren": "include_children",
    "index.explorer.search": "Search",
    "index.explorer.previewEmpty": "Enter a topic query to preview canonical normalization.",
    "index.explorer.emptyTitle": "No explorer query yet",
    "index.explorer.emptyMessage": "Select a venue, year, and topic to inspect normalized query details, counts, relative_frequency, warnings, and evidence papers.",

    "index.domains.kicker": "Domains",
    "index.domains.title": "Domain Overview",
    "index.domains.desc": "Domains expose coarse taxonomy scope. arXiv categories remain domain metadata.",
    "index.venues.kicker": "Venues",
    "index.venues.title": "Venue Overview",
    "index.venues.desc": "Venue cards use index data first and do not fetch every venue's keywords on initial load.",

    "index.keyword.venue": "Keyword venue filter",
    "index.keyword.year": "Keyword year filter",
    "index.keyword.allVenues": "All venues",
    "index.keyword.allYears": "All years",
    "index.keyword.refresh": "Refresh keyword charts",
    "index.keyword.cloud": "Keyword Cloud",
    "index.keyword.cloudDesc": "Keyword view is retained below the topic-first dashboard and loads only when visible.",
    "index.keyword.top": "Top 20 Keywords",
    "index.keyword.topDesc": "Count-only view, kept separate from trend claims.",
    "index.keyword.trends": "Keyword Count Trends",
    "index.keyword.trendsDesc": "Legacy keyword chart. Topic metrics above remain the primary trend surface.",
    "index.keyword.searchPlaceholder": "Search keywords...",

    "footer.tagline": "DeepTrender - structured AI/ML paper trend database",
    "footer.sources.core": "Source evidence is labeled as accepted, preprint, mixed, or unknown when available.",

    "venue.title": "Venue Analysis - DeepTrender",
    "venue.heading": "Select a venue",
    "venue.stat.papers": "Total Papers",
    "venue.stat.years": "Covered Years",
    "venue.cloud": "Keyword Cloud",
    "venue.papers": "Papers by Year",
    "venue.evolution": "Keyword Evolution",
    "venue.table": "Yearly Top Keywords",
    "venue.rank": "Rank",
    "trends.title": "Trend Tracking - DeepTrender",
    "trends.heading": "Keyword Trend Tracking",
    "trends.subheading": "Track long-term shifts in popular research topics.",
    "trends.placeholder": "Type keywords and press Enter, e.g. transformer, diffusion",
    "trends.add": "Add",
    "trends.compare": "Keyword Trend Comparison",
    "trends.clear": "Clear",
    "trends.emerging": "Emerging Keywords",
    "trends.emerging.desc": "Topics growing fastest in recent data.",
    "trends.suggestions": "Popular Keywords",
    "comparison.title": "Venue Comparison - DeepTrender",
    "comparison.heading": "Venue Comparison",
    "comparison.subheading": "Compare keyword distributions across venues.",
    "comparison.year": "Year",
    "comparison.chart": "Keyword Distribution Comparison",
    "arxiv.title": "arXiv Trends - DeepTrender",
    "arxiv.heading": "arXiv Paper Trends",
    "arxiv.subheading": "Inspect publication activity and topics from recent arXiv papers.",
    "arxiv.granularity": "Granularity",
    "arxiv.year": "Year",
    "arxiv.week": "Week",
    "arxiv.day": "Day",
    "arxiv.category": "Category",
    "arxiv.category.all": "All categories",
    "arxiv.series": "Paper Count Trend",
    "arxiv.keywords": "Top Keywords by Time Bucket",
    "arxiv.status": "Data status:",
    "arxiv.points": "Data points:",
  },
  zh: {
    "nav.overview": "概览",
    "nav.domains": "领域",
    "nav.topics": "主题",
    "nav.venues": "会议",
    "nav.explorer": "探索器",
    "nav.arxiv": "arXiv",
    "nav.dataQuality": "数据质量",
    "nav.home": "首页",
    "nav.trends": "趋势追踪",
    "nav.compare": "会议对比",
    "lang.en": "英文",
    "lang.zh": "中文",

    "index.title": "DeepTrender - 结构化 AI/ML 论文趋势数据库",
    "index.hero.kicker": "主题数据探索器",
    "index.hero.title": "DeepTrender",
    "index.hero.desc": "结构化 AI/ML 论文主题、证据、relative_frequency、计数和告警。",
    "index.scope.label": "数据范围",
    "index.scope.preprint": "arXiv 预印本",
    "index.scope.accepted": "会议接收",
    "index.scope.mixed": "结构化混合",
    "index.scope.note.preprint": "当前范围：arXiv 预印本。预印本不等同于会议接收证据。",
    "index.scope.note.accepted": "当前范围：会议接收。证据状态会继续明确标注。",
    "index.scope.note.mixed": "当前范围：结构化混合。接收、预印本、混合和未知证据会分开标注。",
    "index.stat.papers": "结构化论文",
    "index.stat.keywords": "跟踪关键词",
    "index.stat.venues": "覆盖会议",
    "index.stat.years": "年份范围",

    "index.quality.kicker": "数据质量",
    "index.quality.title": "可见告警",
    "index.quality.loading": "正在加载质量检查...",
    "index.quality.empty": "当前质量报告没有告警。",
    "index.quality.reportTitle": "范围化质量报告",
    "index.quality.reportDesc": "指标使用与 MCP 工具一致的告警阈值。",
    "index.quality.sourceBreakdown": "来源分布",

    "index.topics.kicker": "标准主题体系",
    "index.topics.title": "标准主题",
    "index.topics.desc": "主题卡片来自标准 taxonomy。可用时以 relative_frequency 为主，同时显示计数。",
    "index.topics.use": "用于探索器",
    "index.topics.queryScoped": "按查询计算",
    "index.topics.shownExplorer": "在探索器显示",

    "index.topicChart.title": "主题相对频率",
    "index.topicChart.subtitle": "主指标：relative_frequency。计数同步显示。",

    "index.explorer.kicker": "会议-年份-主题探索器",
    "index.explorer.title": "查看主题证据",
    "index.explorer.desc": "默认不包含子主题。",
    "index.explorer.venue": "会议",
    "index.explorer.year": "年份",
    "index.explorer.topic": "主题查询",
    "index.explorer.topicPlaceholder": "transformer、LLM、diffusion...",
    "index.explorer.includeChildren": "包含子主题",
    "index.explorer.search": "查询",
    "index.explorer.previewEmpty": "输入主题后预览标准化结果。",
    "index.explorer.emptyTitle": "尚未查询",
    "index.explorer.emptyMessage": "选择会议、年份和主题后查看标准化查询、计数、relative_frequency、告警和证据论文。",

    "index.domains.kicker": "领域",
    "index.domains.title": "领域概览",
    "index.domains.desc": "领域用于粗粒度分类。arXiv 分类只作为领域元数据。",
    "index.venues.kicker": "会议",
    "index.venues.title": "会议概览",
    "index.venues.desc": "会议卡片优先使用索引数据，首屏不逐个请求关键词。",

    "index.keyword.venue": "关键词会议筛选",
    "index.keyword.year": "关键词年份筛选",
    "index.keyword.allVenues": "全部会议",
    "index.keyword.allYears": "全部年份",
    "index.keyword.refresh": "刷新关键词图表",
    "index.keyword.cloud": "关键词云",
    "index.keyword.cloudDesc": "关键词视图保留在主题优先区域下方，进入视口后再加载。",
    "index.keyword.top": "Top 20 关键词",
    "index.keyword.topDesc": "仅表示计数，不用于趋势结论。",
    "index.keyword.trends": "关键词计数趋势",
    "index.keyword.trendsDesc": "旧关键词图表。上方主题指标仍是主要趋势视图。",
    "index.keyword.searchPlaceholder": "搜索关键词...",

    "footer.tagline": "DeepTrender - 结构化 AI/ML 论文趋势数据库",
    "footer.sources.core": "来源证据会标注为接收、预印本、混合或未知。",

    "venue.title": "会议分析 - DeepTrender",
    "venue.heading": "选择会议",
    "venue.stat.papers": "论文总数",
    "venue.stat.years": "覆盖年份",
    "venue.cloud": "关键词云",
    "venue.papers": "年度论文数",
    "venue.evolution": "关键词演化",
    "venue.table": "年度 Top 关键词",
    "venue.rank": "排名",
    "trends.title": "趋势追踪 - DeepTrender",
    "trends.heading": "关键词趋势追踪",
    "trends.subheading": "追踪研究主题的长期变化。",
    "trends.placeholder": "输入关键词并按回车，例如 transformer, diffusion",
    "trends.add": "添加",
    "trends.compare": "关键词趋势对比",
    "trends.clear": "清空",
    "trends.emerging": "新兴关键词",
    "trends.emerging.desc": "近期增长最快的主题。",
    "trends.suggestions": "热门关键词",
    "comparison.title": "会议对比 - DeepTrender",
    "comparison.heading": "会议对比",
    "comparison.subheading": "对比不同会议的关键词分布。",
    "comparison.year": "年份",
    "comparison.chart": "关键词分布对比",
    "arxiv.title": "arXiv 趋势 - DeepTrender",
    "arxiv.heading": "arXiv 论文趋势",
    "arxiv.subheading": "查看近期 arXiv 论文活动和主题。",
    "arxiv.granularity": "时间粒度",
    "arxiv.year": "年",
    "arxiv.week": "周",
    "arxiv.day": "日",
    "arxiv.category": "分类",
    "arxiv.category.all": "全部分类",
    "arxiv.series": "论文数量趋势",
    "arxiv.keywords": "各时间段 Top 关键词",
    "arxiv.status": "数据状态：",
    "arxiv.points": "数据点：",
  },
};

function getLanguage() {
  const saved = window.localStorage.getItem(SITE_LANG_KEY);
  return saved === "zh" ? "zh" : "en";
}

function translate(key, fallback = "") {
  const language = getLanguage();
  return SITE_I18N[language]?.[key] || SITE_I18N.en[key] || fallback;
}

function applyLanguage() {
  const language = getLanguage();
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = translate(element.dataset.i18n, element.textContent);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = translate(
      element.dataset.i18nPlaceholder,
      element.placeholder,
    );
  });

  const titleKey = document.body?.dataset.i18nTitle;
  if (titleKey) {
    document.title = translate(titleKey, document.title);
  }

  document.querySelectorAll("[data-lang-switch]").forEach((button) => {
    button.classList.toggle("active", button.dataset.langSwitch === language);
  });
}

function switchLanguage(language) {
  window.localStorage.setItem(SITE_LANG_KEY, language === "zh" ? "zh" : "en");
  applyLanguage();
  document.dispatchEvent(new CustomEvent("deeptrender:language-changed"));
}

window.SiteI18n = {
  t: translate,
  getLanguage,
  switchLanguage,
  applyLanguage,
};

document.addEventListener("DOMContentLoaded", applyLanguage);
