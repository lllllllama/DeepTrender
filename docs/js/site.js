const SITE_LANG_KEY = "deeptrender.lang";

const SITE_I18N = {
  en: {
    "nav.home": "Home",
    "nav.venues": "Venue Analysis",
    "nav.trends": "Trend Tracking",
    "nav.compare": "Venue Comparison",
    "nav.arxiv": "arXiv Trends",
    "lang.en": "English",
    "lang.zh": "Chinese",
    "footer.tagline": "DeepTrender - AI paper keyword tracking and trend analytics",
    "footer.sources.core": "Data sources: OpenReview | Semantic Scholar",
    "footer.sources.all": "Data sources: arXiv | OpenReview | Semantic Scholar",
    "index.title": "DeepTrender - AI Paper Trend Analytics",
    "index.stat.papers": "Total Papers",
    "index.stat.keywords": "Tracked Keywords",
    "index.stat.venues": "Covered Venues",
    "index.stat.years": "Year Range",
    "index.filter.venue": "Venue",
    "index.filter.venue.all": "All venues",
    "index.filter.year": "Year",
    "index.filter.year.all": "All years",
    "index.refresh": "Refresh",
    "index.cloud": "Keyword Cloud",
    "index.top": "Top 20 Keywords",
    "index.trends": "Keyword Trends",
    "index.search": "Search keywords...",
    "index.venues": "Venue Overview",
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
    "arxiv.subheading": "Inspect publication activity and hot topics from recent arXiv papers.",
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
    "nav.home": "首页",
    "nav.venues": "会议分析",
    "nav.trends": "趋势追踪",
    "nav.compare": "会议对比",
    "nav.arxiv": "arXiv 趋势",
    "lang.en": "English",
    "lang.zh": "中文",
    "footer.tagline": "DeepTrender - AI 论文关键词追踪与趋势分析",
    "footer.sources.core": "数据来源：OpenReview | Semantic Scholar",
    "footer.sources.all": "数据来源：arXiv | OpenReview | Semantic Scholar",
    "index.title": "DeepTrender - AI 论文趋势分析",
    "index.stat.papers": "论文总数",
    "index.stat.keywords": "已追踪关键词",
    "index.stat.venues": "覆盖会议",
    "index.stat.years": "年份范围",
    "index.filter.venue": "会议",
    "index.filter.venue.all": "全部会议",
    "index.filter.year": "年份",
    "index.filter.year.all": "全部年份",
    "index.refresh": "刷新",
    "index.cloud": "关键词词云",
    "index.top": "Top 20 关键词",
    "index.trends": "关键词趋势",
    "index.search": "搜索关键词...",
    "index.venues": "会议概览",
    "venue.title": "会议分析 - DeepTrender",
    "venue.heading": "选择会议",
    "venue.stat.papers": "论文总数",
    "venue.stat.years": "覆盖年份",
    "venue.cloud": "关键词词云",
    "venue.papers": "年度论文数量",
    "venue.evolution": "关键词演化",
    "venue.table": "年度 Top 关键词",
    "venue.rank": "排名",
    "trends.title": "趋势追踪 - DeepTrender",
    "trends.heading": "关键词趋势追踪",
    "trends.subheading": "追踪热门研究主题的长期变化。",
    "trends.placeholder": "输入关键词并按回车，例如 transformer, diffusion",
    "trends.add": "添加",
    "trends.compare": "关键词趋势对比",
    "trends.clear": "清空",
    "trends.emerging": "新兴关键词",
    "trends.emerging.desc": "近期增长最快的主题。",
    "trends.suggestions": "热门关键词",
    "comparison.title": "会议对比 - DeepTrender",
    "comparison.heading": "会议对比分析",
    "comparison.subheading": "对比不同会议的关键词分布。",
    "comparison.year": "年份",
    "comparison.chart": "关键词分布对比",
    "arxiv.title": "arXiv 趋势 - DeepTrender",
    "arxiv.heading": "arXiv 论文趋势",
    "arxiv.subheading": "查看近期 arXiv 论文的时间趋势与热门主题。",
    "arxiv.granularity": "时间粒度",
    "arxiv.year": "年",
    "arxiv.week": "周",
    "arxiv.day": "日",
    "arxiv.category": "分类",
    "arxiv.category.all": "全部分类",
    "arxiv.series": "论文数量趋势",
    "arxiv.keywords": "各时间段热门关键词",
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
