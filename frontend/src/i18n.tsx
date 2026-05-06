import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";

const STORAGE_KEY = "review-integrity-locale";

export type Locale = "en" | "ru";

const translations = {
  en: {
    languageSwitch: {
      label: "Language",
      ariaLabel: "Switch site language",
      english: "EN",
      russian: "RU",
    },
    themeSwitch: {
      label: "Theme",
      ariaLabel: "Switch color theme",
      light: "Light",
      dark: "Dark",
    },
    common: {
      ready: "Ready",
      running: "Running",
      clear: "Clear",
      retry: "Retry",
      tryAgain: "Try again",
      preview: "Preview",
      rows: "rows",
      reviews: "reviews",
      signalGroups: "signal groups",
      detectorsActive: "detectors active",
      rowsAvailable: "rows available",
      tablePreview: "Table preview",
      detectorPreview: "Detector preview",
      explainabilityPreview: "Explanation preview",
      sourceLoaded: "Source loaded",
      progress: "Progress",
      complete: "complete",
    },
    hero: {
      eyebrow: "Partner review risk control",
      title: "Detect review manipulation before it damages brand trust.",
      description:
        "A business-facing system for companies that sell through contractors, dealers, marketplaces, or partner storefronts. It helps verify whether external reviews can be trusted before cooperation is expanded.",
      audienceLine: "For manufacturers, marketplaces, retailers, and brand protection teams.",
      primaryCta: "Run review check",
      secondaryCta: "Open demo",
      badges: {
        nlp: "Review text analysis",
        anomaly: "Rating anomalies",
        patterns: "Partner risk signals",
        scraping: "Adaptive data import",
      },
      flowSteps: ["Data", "Analysis", "Risk report"],
      previewEyebrow: "Preview analytics",
      previewTitle: "What happens after launch",
      onboardingTitle: "No metrics before the check",
      onboardingDescription:
        "The first screen explains the workflow. Real scores, charts, and suspicious reviews appear only after you upload data or open the demo report.",
      onboardingSteps: [
        "Upload a file, paste HTML, enter a page URL, or connect an API source.",
        "The system normalizes reviews and searches for rating manipulation signals.",
        "You receive a risk report with reasons and items for manual review.",
      ],
      outputTitle: "After analysis the report will show",
      outputItems: [
        "overall risk profile",
        "why the system flagged the page",
        "suspicious review examples",
        "recommended manual checks",
      ],
      reportPreviewTitle: "Future report structure",
      reportPreviewDescription: "A visual outline of the blocks that appear only after analysis.",
      reportPreviewBadge: "after launch",
      reportPreviewRows: ["Risk profile", "Evidence layer", "Manual review queue"],
      analysisScope: ["review text", "posting rhythm", "rating shifts", "author patterns"],
      decisionLabel: "System verdict",
      evidenceTitle: "Why risk is elevated",
      recommendedAction: "Recommended action",
      recommendedActionText: "Send flagged reviews and author clusters to manual review before trusting the partner page.",
      riskScore: "Risk",
      reviewActivity: "Review activity",
      reviewVolume: "Review volume",
      recentCadence: "Publication spike detected",
      manipulationProbability: "Manipulation probability",
      confidence: "Confidence",
      flaggedReviews: "Flagged reviews",
      manualReview: "Manual review",
      insightsTitle: "Strongest warning signals",
      insights: [
        "Unnatural review burst after a quiet period",
        "Repeated promotional wording across different authors",
        "Extreme ratings with weak product-specific details",
      ],
    },
    businessValue: {
      eyebrow: "Business scenario",
      title: "For brands that need to trust partner review quality",
      description:
        "The service helps a company verify whether an external seller, contractor, dealer, or marketplace page is building trust honestly or hiding reputational risk behind inflated ratings.",
      scenarioTitle: "Typical use case",
      scenarioText:
        "A partner reports that product feedback is excellent on a third-party site. Before expanding cooperation, the brand runs this page through the system and receives a risk profile: suspicious review clusters, rating bursts, weak evidence, and items that require manual review.",
      scenarioSteps: [
        "Partner shares an external page with strong ratings.",
        "The company uploads a file, HTML page, or API source.",
        "The system returns risk signals and reviews for manual follow-up.",
      ],
      audienceTitle: "Who needs it",
      audience: [
        {
          title: "Large manufacturers",
          description: "Control how products are represented by dealers, distributors, and regional partners.",
        },
        {
          title: "Marketplaces and retail chains",
          description: "Detect sellers that inflate ratings and damage buyer trust across the platform.",
        },
        {
          title: "Brand safety teams",
          description: "Reduce reputation, legal, and customer-support risks before they become public incidents.",
        },
      ],
      risksTitle: "Signals the system looks for",
      risks: [
        {
          title: "Review bursts",
          description: "Many similar reviews appear in a short period after long silence.",
        },
        {
          title: "Text similarity",
          description: "Different authors repeat the same phrasing, selling points, or emotional template.",
        },
        {
          title: "Rating imbalance",
          description: "The rating curve looks too positive or changes sharply without a natural explanation.",
        },
        {
          title: "Weak evidence",
          description: "Reviews praise the product but lack concrete usage details, photos, or credible context.",
        },
      ],
    },
    controlPanel: {
      eyebrow: "Review check launch",
      title: "Start a partner page analysis",
      description: "Choose the source, collection depth, and run the model to receive a business-readable risk report.",
      sourceSectionTitle: "Data source",
      sourceSectionHelper: "Choose how the system should receive the review sample for analysis.",
      sourceModes: {
        url: {
          helper: "Fetch a live marketplace page through ScrapingBee.",
        },
        html: {
          helper: "Paste or upload a local snapshot for deterministic testing.",
        },
        records: {
          label: "Structured data",
          helper: "Run full rating manipulation analysis on prepared review records.",
        },
      },
      fields: {
        productPageUrl: "Product page URL",
        productPageUrlHelper: "Works best when the review blocks are accessible on the fetched page.",
        sourceLabel: "Source label",
        sourceLabelHelper: "Optional label or canonical URL for the snapshot.",
        htmlSource: "HTML source",
        htmlSourceHelper: "Paste raw HTML from the saved page snapshot.",
        analysisModeTitle: "Analysis mode",
        analysisModeHelper: "Choose the depth of the next review check.",
        advancedTitle: "Advanced settings",
        advancedHelper: "Optional overrides for power users and debugging sessions.",
        manualWait: "Manual wait override",
        manualWaitHelper: "Optional wait in milliseconds, used instead of the analysis mode default. Keep it at 0-30000.",
        snapshotHelper: "Snapshot helper",
        snapshotHelperText:
          "For HTML mode you can keep the source label to preserve where the sample came from.",
      },
      depthModes: {
        fast: {
          label: "Fast",
          helper: "Quicker fetch, lighter waiting, rapid preview.",
        },
        standard: {
          label: "Standard",
          helper: "Balanced timing and model pass for the main workflow.",
        },
        deep: {
          label: "Deep",
          helper: "Longer wait and a more investigative review collection pass.",
        },
      },
      placeholders: {
        productUrl: "https://example.com/product/reviews",
        sourceLabel: "local-snapshot or https://example.com/product",
        html: "<html>...</html>",
        waitMs: "5000",
        snapshotHelper: "optional source label",
      },
      actions: {
        analyze: "Run review check",
        analyzing: "Analyzing...",
        demo: "Show demo report",
      },
      submitTitle: "Ready to analyze",
      submitDescription: "Start with a real page or open a demo report to show the full workflow safely.",
    },
    resultsPanel: {
      eyebrow: "Review verification results",
      title: "Risk report for the checked review page",
      description:
        "The report combines the overall risk score, review dynamics, anomaly categories, and suspicious examples in one decision-ready view.",
      trustworthySplit: "Trustworthy / suspicious split",
      trendCharts: "Trend and anomaly charts",
      waitingBadge: "Waiting for analysis",
      unexpectedFailure: "Unexpected analysis failure.",
    },
    resultsSuccess: {
      riskProfile: "Risk profile",
      riskScore: "Risk score",
      manipulationProbability: "Manipulation probability",
      confidence: "Confidence",
      collectedReviews: "Collected reviews",
      flaggedReviews: "Flagged reviews",
      manualReview: "Manual review",
      explainabilityEyebrow: "Explainability summary",
      explainabilityTitle: "Why this risk profile was assigned",
      explainabilityDescription:
        "A short decision digest that surfaces the strongest product-level signals before you dive into the deeper explainability section below.",
      decisionDigest: "Decision digest",
      trustSplitEyebrow: "Trustworthiness split",
      trustSplitTitle: "Trustworthy / suspicious / uncertain",
      temporalEyebrow: "Temporal activity",
      temporalTitle: "Review timeline and suspicious cadence",
      timeAware: "Time-aware",
      anomalyEyebrow: "Anomaly profile",
      anomalyTitle: "Detected anomaly categories",
      reviewSeries: "Reviews",
      suspiciousSeries: "Suspicious",
      countSeries: "Count",
    },
    pipeline: {
      eyebrow: "Pipeline",
      title: "Review analysis stages",
      description:
        "A transparent view of how the system turns a page or dataset into a final risk profile for business review.",
      active: "Pipeline active",
      complete: "Pipeline complete",
      waiting: "Waiting",
    },
    emptyState: {
      eyebrow: "Report is not generated yet",
      title: "Choose a source and launch the check",
      description:
        "After analysis, this area turns into a risk report with evidence, anomaly dynamics, and suspicious reviews for manual review.",
      setupAction: "Choose source",
      demoAction: "Open demo",
      cards: [
        {
          title: "Risk profile",
          description: "Overall risk level and model confidence after the check.",
        },
        {
          title: "Evidence",
          description: "Bursts, repeated wording, rating shifts, and weak review details.",
        },
        {
          title: "Suspicious reviews",
          description: "Ranked examples that should be checked manually.",
        },
        {
          title: "Decision hint",
          description: "A short next step before trusting a partner review page.",
        },
      ],
    },
    errorState: {
      title: "Analysis could not be completed",
      helper: "Check the page URL or supplied review data and then retry the request.",
      errors: {
        ANALYSIS_FAILED: {
          message: "The backend could not finish the analysis run.",
          helper: "Check the backend logs for the root cause, then retry the request.",
        },
        INPUT_SOURCE_MISSING: {
          message: "No analysis source was provided.",
          helper: "Choose URL, HTML, or Site Data and provide the required input.",
        },
        INVALID_INPUT: {
          message: "The backend rejected the supplied input.",
          helper: "Review the entered data and retry the request.",
        },
        INVALID_RESPONSE: {
          message: "The backend returned an invalid response.",
          helper: "Refresh the page and retry. If it repeats, check the API logs.",
        },
        INVALID_URL: {
          message: "The product URL is invalid.",
          helper: "Use a full URL that starts with http:// or https://.",
        },
        INVALID_SCRAPING_WAIT: {
          message: "The manual wait value is too large for the scraping timeout.",
          helper: "Use 0-30000 ms, or leave the field empty and let the analysis mode choose a safe value.",
        },
        IMPORT_SOURCE_FETCH_FAILED: {
          message: "The backend could not fetch the API/data source.",
          helper: "Check that the URL is public and reachable, then retry or upload the file manually.",
        },
        NETWORK_ERROR: {
          message: "The frontend could not reach the analysis backend.",
          helper: "Make sure Flask is running on port 5000, then retry.",
        },
        RATING_ARTIFACTS_MISSING: {
          message: "Rating anti-fraud model artifacts are missing.",
          helper: "Run the rating model training pipeline before using Site Data mode.",
        },
        REQUEST_BODY_INVALID: {
          message: "The API request body is invalid.",
          helper: "Refresh the page and retry the request.",
        },
        REVIEW_ARTIFACTS_MISSING: {
          message: "Review model artifacts are missing.",
          helper: "Run the review model training pipeline before analyzing pages.",
        },
        SCRAPING_BLOCKED: {
          message: "The marketplace returned a bot-protection or blocked page instead of reviews.",
          helper: "Use HTML snapshot mode for a stable check, or retry with a lower analysis depth.",
        },
        SCRAPINGBEE_NOT_CONFIGURED: {
          message:
            "ScrapingBee is not configured on the backend. Set `SCRAPINGBEE_API_KEY` in `.env` or the process environment.",
          helper: "Restart Flask after changing backend environment variables, then retry the request.",
        },
        SCRAPEDO_NOT_CONFIGURED: {
          message:
            "Scrape.do is not configured on the backend. Set `SCRAPEDO_API_KEY` in `.env` or the process environment.",
          helper: "Restart Flask after changing backend environment variables, then retry the request.",
        },
        SCRAPING_FETCH_FAILED: {
          message: "ScrapingBee could not fetch the marketplace page.",
          helper: "Try HTML snapshot mode, reduce the analysis depth, or check external collector credits/proxy availability.",
        },
        SCRAPING_RATE_LIMITED: {
          message: "The external collection service hit a rate limit or credits issue.",
          helper: "Check ScrapingBee/Scrape.do balance and limits, or use HTML snapshot mode to continue without live scraping.",
        },
        SCRAPING_SERVICE_NOT_CONFIGURED: {
          message: "No live scraping provider is configured on the backend.",
          helper: "Set `SCRAPINGBEE_API_KEY` or `SCRAPEDO_API_KEY`, restart Flask, or use HTML/file mode.",
        },
        SCRAPING_TIMEOUT: {
          message: "The external collection service did not return the page before the backend timeout.",
          helper: "Reduce manual wait, use Fast/Standard mode, or paste an HTML snapshot for deterministic analysis.",
        },
        UNKNOWN_ERROR: {
          message: "An unexpected analysis error occurred.",
          helper: "Retry the request. If it repeats, check the backend logs.",
        },
      },
    },
    loadingState: {
      title: "Building the analysis profile",
      description:
        "The system is collecting the page, extracting reviews, generating features, and assembling the final score.",
    },
    detectorGrid: {
      eyebrow: "Detector Cards",
      title: "Detector signals",
      description:
        "Each card turns model and heuristic output into a clear product-level risk signal.",
      detectorScore: "Detector score",
      status: "Status",
    },
    explainability: {
      eyebrow: "Explanation layer",
      title: "Why the system made this decision",
      description:
        "A compact explanation layer for defense, moderation, and model interpretation. It surfaces the strongest factors that drove the final risk profile.",
      liveWeights: "Live factor weights",
      decisionNarrative: "Decision narrative",
      decisionNarrativeDescription:
        "The system combines text similarity, temporal anomalies, rating drift, reviewer behavior, and bilingual slang cues to build a moderation-oriented explanation.",
      topFactors: "Top contributing factors",
      topFactorsDescription:
        "Weighted contribution bars make it clear which signals dominated the final decision.",
    },
    suspiciousTable: {
      eyebrow: "Suspicious Reviews Table",
      title: "Ranked suspicious review examples",
      description:
        "A compact moderation-oriented table with sort, filter, and language-aware evidence for the most suspicious reviews.",
      filterPlaceholder: "Filter by text, reason, author, or slang terms",
      severity: {
        all: "All severities",
        high: "High",
        medium: "Medium",
        low: "Low",
      },
      language: {
        all: "All language profiles",
        suspicious: "Suspicious",
        mixed: "Mixed",
        organic: "Organic",
        neutral: "Neutral",
      },
      sort: {
        suspiciousness: "Sort by suspiciousness",
        date: "Sort by date",
        rating: "Sort by rating",
      },
      triage: {
        all: "All triage states",
        confidentSuspicious: "Confident suspicious",
        needsManualReview: "Needs manual review",
        confidentClean: "Confident clean",
      },
      waitingTitle: "Suspicious review table is waiting for data",
      waitingDescription:
        "Run the detector to unlock the ranked table with language evidence, filtering, sorting, and reviewer trust levels.",
      emptyTitle: "No rows match the current filters",
      emptyDescription:
        "Try another search query or relax the severity and language filters to inspect more of the suspicious review set.",
      summary: {
        visible: "Visible rows",
        highRisk: "High risk",
        manualReview: "Needs review",
        avgRisk: "Avg. risk",
      },
      columns: {
        reviewText: "Review text",
        rating: "Rating",
        suspiciousness: "Suspiciousness",
        reason: "Flag reason",
        author: "Author / trust",
        date: "Date",
      },
      labels: {
        rating: "Rating",
        suspiciousness: "Suspiciousness",
        reason: "Reason",
        author: "Author",
        date: "Date",
        templateCluster: "Template cluster",
        photoEvidence: "Photo evidence",
        duplicatePhotoCluster: "Duplicate photo cluster",
        photoReuse: "Photo reuse",
        photoTemporalCluster: "Timed photo cluster",
        photoTemporalClusterScore: "Photo burst",
        photoMismatch: "Photo mismatch",
        photoTextMismatch: "Photo/text mismatch",
        stockMarketingPhoto: "Stock/marketing photo",
        stockMarketingScore: "Stock-photo score",
        photoOcrText: "OCR text signal",
        photoOcrScore: "Photo OCR",
        syntheticImageHint: "AI/synthetic hint",
        syntheticImageScore: "AI-image hint",
        aiTextScore: "AI-text score",
        slangRisk: "Slang risk",
        grounding: "Grounding",
        uncertainty: "Uncertainty",
        oodDrift: "OOD drift",
      },
    },
    dataImport: {
      title: "Structured site data",
      description:
        "Upload a file or connect an API source. The importer detects the file format automatically and maps common columns to review fields.",
      sources: {
        file: "File",
        api: "API",
      },
      expectedStructure: "Expected structure",
      fetchTitle: "Fetch from API",
      fetchDescription:
        "Enter a public endpoint and run a GET request. The importer will detect JSON, JSONL, CSV/TSV, Excel, or HTML responses and normalize them into review records.",
      fetchAction: "Fetch data",
      chooseFile: "Choose file",
      apiPlaceholder: "https://api.example.com/reviews",
      readyTitle: "Import is ready",
      readyDescription:
        "The structure is valid and can be sent directly into the site-data analysis pipeline.",
      warningTitle: "Import completed with warnings",
      errorTitle: "Structure validation failed",
      errorDescription:
        "The imported source is missing fields required by the model. Fix the structure and try the import again.",
      previewTitle: "Normalized preview",
      previewDescription: "The first 5-10 rows after the source structure has been normalized.",
      previewHeaders: {
        item_id: "item_id",
        user: "user",
        rating: "rating",
        timestamp: "timestamp",
        text: "text",
        ip: "ip",
        geo: "geo",
      },
      fileDrop: {
        file: "Drop a file here or click to upload",
        helper:
          "Supported formats: Excel, CSV/TSV, JSON/JSONL, HTML. The importer detects the format automatically, shows a preview, and validates the data before analysis.",
      },
      importLoadingTitle: "Normalizing imported data...",
      importLoadingDescription:
        "The importer is validating the format, extracting records, and building a normalized payload for the anti-fraud pipeline.",
      importFailedTitle: "Data import failed",
      runAnalysis: "Run analysis",
    },
  },
  ru: {
    languageSwitch: {
      label: "Язык",
      ariaLabel: "Переключить язык сайта",
      english: "EN",
      russian: "RU",
    },
    themeSwitch: {
      label: "Тема",
      ariaLabel: "Переключить цветовую тему",
      light: "Свет",
      dark: "Тьма",
    },
    common: {
      ready: "Готово",
      running: "В работе",
      clear: "Очистить",
      retry: "Повторить",
      tryAgain: "Попробовать снова",
      preview: "Превью",
      rows: "записей",
      reviews: "отзывов",
      signalGroups: "групп сигналов",
      detectorsActive: "активных детекторов",
      rowsAvailable: "строк доступно",
      tablePreview: "Превью таблицы",
      detectorPreview: "Превью детекторов",
      explainabilityPreview: "Превью объяснений",
      sourceLoaded: "Источник загружен",
      progress: "Прогресс",
      complete: "завершено",
    },
    hero: {
      eyebrow: "Контроль отзывов у партнеров",
      title: "Выявляйте накрутку отзывов до удара по репутации бренда.",
      description:
        "Веб-сервис для компаний, которые продают товары через подрядчиков, дилеров, маркетплейсы и партнерские витрины. Система помогает понять, можно ли доверять внешним отзывам перед расширением сотрудничества.",
      audienceLine: "Для производителей, маркетплейсов, ритейла и команд защиты бренда.",
      primaryCta: "Запустить проверку",
      secondaryCta: "Открыть демо",
      badges: {
        nlp: "Анализ текста отзывов",
        anomaly: "Рейтинговые аномалии",
        patterns: "Риски партнеров",
        scraping: "Автоимпорт данных",
      },
      flowSteps: ["Данные", "Анализ", "Риск-отчет"],
      previewEyebrow: "Предпросмотр аналитики",
      previewTitle: "Что произойдет после запуска",
      onboardingTitle: "Без метрик до проверки",
      onboardingDescription:
        "Первый экран объясняет сценарий работы. Реальные оценки риска, графики и подозрительные отзывы появятся только после загрузки данных или открытия демо-отчета.",
      onboardingSteps: [
        "Загрузите файл, вставьте HTML, укажите URL страницы или подключите API-источник.",
        "Система нормализует отзывы и ищет признаки накрутки рейтинга.",
        "Вы получите отчет о рисках с причинами и элементами для ручной проверки.",
      ],
      outputTitle: "После анализа в отчете появятся",
      outputItems: [
        "общий риск-профиль",
        "причины срабатывания системы",
        "примеры подозрительных отзывов",
        "рекомендации для ручной проверки",
      ],
      reportPreviewTitle: "Структура будущего отчета",
      reportPreviewDescription: "Визуальный контур блоков, которые появятся только после анализа.",
      reportPreviewBadge: "после запуска",
      reportPreviewRows: ["Риск-профиль", "Слой доказательств", "Очередь ручной проверки"],
      analysisScope: ["тексты отзывов", "ритм публикаций", "сдвиги рейтинга", "паттерны авторов"],
      decisionLabel: "Вердикт системы",
      evidenceTitle: "Почему риск повышен",
      recommendedAction: "Что сделать дальше",
      recommendedActionText: "Перед доверием к партнерской странице проверить подозрительные отзывы и кластеры авторов вручную.",
      riskScore: "Риск",
      reviewActivity: "Активность отзывов",
      reviewVolume: "Объем отзывов",
      recentCadence: "Обнаружен всплеск публикаций",
      manipulationProbability: "Вероятность накрутки",
      confidence: "Уверенность",
      flaggedReviews: "Подозрительные отзывы",
      manualReview: "Ручная проверка",
      insightsTitle: "Главные сигналы риска",
      insights: [
        "Резкий всплеск отзывов после периода тишины",
        "Повторяющиеся рекламные формулировки у разных авторов",
        "Крайние оценки без конкретных деталей о товаре",
      ],
    },
    businessValue: {
      eyebrow: "Бизнес-сценарий",
      title: "Для компаний, которым важно доверять отзывам у партнеров",
      description:
        "Сервис помогает понять, честно ли внешний продавец, подрядчик, дилер или страница маркетплейса формирует доверие к товару, либо за высоким рейтингом скрыт репутационный риск.",
      scenarioTitle: "Типовой сценарий",
      scenarioText:
        "Партнер сообщает, что на стороннем сайте у товара отличные отзывы. Перед расширением сотрудничества бренд проверяет страницу через систему и получает риск-профиль: подозрительные кластеры отзывов, всплески рейтинга, слабые доказательства и элементы, требующие ручной проверки.",
      scenarioSteps: [
        "Партнер показывает внешнюю страницу с высоким рейтингом.",
        "Компания загружает файл, HTML-страницу или API-источник.",
        "Система выдает сигналы риска и отзывы для ручной проверки.",
      ],
      audienceTitle: "Кому это нужно",
      audience: [
        {
          title: "Крупные производители",
          description: "Контролируют, как дилеры, дистрибьюторы и региональные партнеры представляют товар.",
        },
        {
          title: "Маркетплейсы и ритейл",
          description: "Выявляют продавцов, которые накручивают рейтинг и снижают доверие покупателей.",
        },
        {
          title: "Команды защиты бренда",
          description: "Снижают репутационные, юридические и клиентские риски до публичного конфликта.",
        },
      ],
      risksTitle: "Какие сигналы ищет система",
      risks: [
        {
          title: "Всплески отзывов",
          description: "Много похожих отзывов появляется за короткий период после долгой паузы.",
        },
        {
          title: "Сходство текстов",
          description: "Разные авторы повторяют одинаковые фразы, преимущества товара или эмоциональный шаблон.",
        },
        {
          title: "Перекос рейтинга",
          description: "Кривая оценок выглядит слишком положительной или резко меняется без естественной причины.",
        },
        {
          title: "Слабые доказательства",
          description: "Отзывы хвалят товар, но не содержат деталей использования, фото или достоверного контекста.",
        },
      ],
    },
    controlPanel: {
      eyebrow: "Запуск проверки отзывов",
      title: "Проверка партнерской страницы",
      description: "Выберите источник, глубину сбора и запустите модель, чтобы получить понятный бизнесу отчет о рисках.",
      sourceSectionTitle: "Источник данных",
      sourceSectionHelper: "Выберите, как система должна получить набор отзывов для проверки.",
      sourceModes: {
        url: {
          helper: "Получает живую страницу маркетплейса через подключенный сборщик данных.",
        },
        html: {
          helper: "Вставьте или загрузите локальный снимок страницы для повторяемой проверки.",
        },
        records: {
          label: "Структурированные данные",
          helper: "Запускает полный анализ накрутки рейтингов на структурированных данных.",
        },
      },
      fields: {
        productPageUrl: "URL страницы товара",
        productPageUrlHelper: "Лучше всего работает, когда блоки отзывов доступны на полученной странице.",
        sourceLabel: "Метка источника",
        sourceLabelHelper: "Необязательная метка или исходный URL для сохраненного снимка.",
        htmlSource: "HTML-источник",
        htmlSourceHelper: "Вставьте сырой HTML из сохраненного снимка страницы.",
        analysisModeTitle: "Режим анализа",
        analysisModeHelper: "Выберите глубину проверки для следующего запуска.",
        advancedTitle: "Расширенные настройки",
        advancedHelper: "Дополнительные параметры для отладки и ручных проверок.",
        manualWait: "Ручное ожидание",
        manualWaitHelper: "Необязательное ожидание в миллисекундах вместо значения режима анализа. Безопасный диапазон: 0-30000.",
        snapshotHelper: "Подсказка снимка",
        snapshotHelperText:
          "В HTML-режиме можно сохранить метку источника, чтобы не потерять происхождение образца.",
      },
      depthModes: {
        fast: {
          label: "Быстро",
          helper: "Быстрый сбор: меньше ожидания и короткий предпросмотр.",
        },
        standard: {
          label: "Стандарт",
          helper: "Баланс ожидания и основного прохода модели.",
        },
        deep: {
          label: "Глубоко",
          helper: "Дольше ждёт страницу и глубже собирает отзывы.",
        },
      },
      placeholders: {
        productUrl: "https://example.com/product/reviews",
        sourceLabel: "local-snapshot или https://example.com/product",
        html: "<html>...</html>",
        waitMs: "5000",
        snapshotHelper: "необязательная метка источника",
      },
      actions: {
        analyze: "Запустить проверку",
        analyzing: "Идет анализ...",
        demo: "Показать демо",
      },
      submitTitle: "Все готово к анализу",
      submitDescription: "Запустите реальную проверку или откройте демо-отчет, чтобы безопасно показать полный сценарий.",
    },
    resultsPanel: {
      eyebrow: "Результаты проверки отзывов",
      title: "Отчет о рисках проверенной страницы",
      description:
        "Отчет объединяет общий риск-профиль, динамику отзывов, категории аномалий и подозрительные примеры в одном представлении для принятия решения.",
      trustworthySplit: "Надежные / подозрительные",
      trendCharts: "Графики трендов и аномалий",
      waitingBadge: "Ожидает запуска",
      unexpectedFailure: "Непредвиденный сбой анализа.",
    },
    resultsSuccess: {
      riskProfile: "Риск-профиль",
      riskScore: "Риск",
      manipulationProbability: "Вероятность накрутки",
      confidence: "Уверенность",
      collectedReviews: "Собрано отзывов",
      flaggedReviews: "Выявлено отзывов",
      manualReview: "Ручная проверка",
      explainabilityEyebrow: "Сводка объяснений",
      explainabilityTitle: "Почему был назначен этот риск-профиль",
      explainabilityDescription:
        "Короткая сводка показывает самые сильные сигналы уровня продукта до погружения в детальный раздел объяснений ниже.",
      decisionDigest: "Сводка решения",
      trustSplitEyebrow: "Распределение доверия",
      trustSplitTitle: "Надежные / подозрительные / неопределенные",
      temporalEyebrow: "Временная активность",
      temporalTitle: "Таймлайн отзывов и подозрительная динамика",
      timeAware: "С учетом времени",
      anomalyEyebrow: "Профиль аномалий",
      anomalyTitle: "Обнаруженные категории аномалий",
      reviewSeries: "Отзывы",
      suspiciousSeries: "Подозрительные",
      countSeries: "Количество",
    },
    pipeline: {
      eyebrow: "Этапы",
      title: "Этапы анализа отзывов",
      description:
        "Прозрачный вид на то, как система превращает страницу или набор данных в итоговый риск-профиль для бизнес-проверки.",
      active: "Анализ выполняется",
      complete: "Анализ завершен",
      waiting: "Ожидание",
    },
    emptyState: {
      eyebrow: "Отчет еще не сформирован",
      title: "Выберите источник и запустите проверку",
      description:
        "После анализа здесь появится риск-отчет с доказательствами, динамикой аномалий и подозрительными отзывами для ручной проверки.",
      setupAction: "Выбрать источник",
      demoAction: "Открыть демо",
      cards: [
        {
          title: "Риск-профиль",
          description: "Общий уровень риска и уверенность модели после проверки.",
        },
        {
          title: "Доказательства",
          description: "Всплески, повторы текста, сдвиги рейтинга и слабые детали отзывов.",
        },
        {
          title: "Подозрительные отзывы",
          description: "Ранжированные примеры, которые стоит проверить вручную.",
        },
        {
          title: "Подсказка решения",
          description: "Короткий следующий шаг перед доверием к странице партнера.",
        },
      ],
    },
    errorState: {
      title: "Анализ не удалось завершить",
      helper: "Проверь URL страницы или загруженные данные отзывов, а затем повтори запрос.",
      errors: {
        ANALYSIS_FAILED: {
          message: "Сервер не смог завершить анализ.",
          helper: "Проверь логи сервера, устрани причину и повтори запрос.",
        },
        INPUT_SOURCE_MISSING: {
          message: "Источник для анализа не передан.",
          helper: "Выбери URL, HTML или структурированные данные и заполни нужные поля.",
        },
        INVALID_INPUT: {
          message: "Сервер отклонил переданные данные.",
          helper: "Проверь введённые данные и повтори запрос.",
        },
        INVALID_RESPONSE: {
          message: "Сервер вернул некорректный ответ.",
          helper: "Обнови страницу и повтори запрос. Если ошибка повторится, проверь API-логи.",
        },
        INVALID_URL: {
          message: "URL страницы товара некорректен.",
          helper: "Используй полный URL, который начинается с http:// или https://.",
        },
        INVALID_SCRAPING_WAIT: {
          message: "Ручное ожидание слишком большое для тайм-аута сбора данных.",
          helper: "Поставь 0-30000 мс или очисти поле, чтобы режим анализа сам выбрал безопасное значение.",
        },
        IMPORT_SOURCE_FETCH_FAILED: {
          message: "Backend не смог получить API-источник или файл данных.",
          helper: "Проверь, что URL публичный и доступный, затем повтори импорт или загрузи файл вручную.",
        },
        NETWORK_ERROR: {
          message: "Интерфейс не смог подключиться к серверу анализа.",
          helper: "Убедись, что Flask запущен на порту 5000, затем повтори запрос.",
        },
        RATING_ARTIFACTS_MISSING: {
          message: "Артефакты модели проверки рейтингов отсутствуют.",
          helper: "Запусти обучение модели рейтингов перед режимом структурированных данных.",
        },
        REQUEST_BODY_INVALID: {
          message: "Тело API-запроса некорректно.",
          helper: "Обнови страницу и повтори запрос.",
        },
        REVIEW_ARTIFACTS_MISSING: {
          message: "Артефакты review-модели отсутствуют.",
          helper: "Запусти обучение review-модели перед анализом страниц.",
        },
        SCRAPING_BLOCKED: {
          message: "Маркетплейс вернул защитную или заблокированную страницу вместо отзывов.",
          helper: "Используй HTML-снимок для стабильной проверки или повтори запуск с меньшей глубиной анализа.",
        },
        SCRAPINGBEE_NOT_CONFIGURED: {
          message:
            "Сервис сбора данных не настроен на сервере. Укажи `SCRAPINGBEE_API_KEY` в `.env` или переменных окружения процесса.",
          helper: "После изменения переменных окружения перезапусти Flask, затем повтори запрос.",
        },
        SCRAPEDO_NOT_CONFIGURED: {
          message:
            "Scrape.do не настроен на сервере. Укажи `SCRAPEDO_API_KEY` в `.env` или переменных окружения процесса.",
          helper: "После изменения переменных окружения перезапусти Flask, затем повтори запрос.",
        },
        SCRAPING_FETCH_FAILED: {
          message: "Внешний сервис сбора не смог получить страницу маркетплейса.",
          helper: "Попробуй HTML-режим, уменьши глубину анализа или проверь лимиты и прокси в сервисах сбора.",
        },
        SCRAPING_RATE_LIMITED: {
          message: "Внешний сервис сбора уперся в лимит запросов или баланс.",
          helper: "Проверь баланс и лимиты ScrapingBee/Scrape.do или используй HTML-снимок, чтобы продолжить без живого сбора.",
        },
        SCRAPING_SERVICE_NOT_CONFIGURED: {
          message: "На backend не настроен ни один провайдер живого сбора страниц.",
          helper: "Укажи `SCRAPINGBEE_API_KEY` или `SCRAPEDO_API_KEY`, перезапусти Flask или используй HTML/файл.",
        },
        SCRAPING_TIMEOUT: {
          message: "Сервис сбора не вернул страницу до тайм-аута сервера.",
          helper: "Уменьши ручное ожидание, используй Быстро/Стандарт или вставь HTML-снимок для стабильной проверки.",
        },
        UNKNOWN_ERROR: {
          message: "Произошла непредвиденная ошибка анализа.",
          helper: "Повтори запрос. Если ошибка повторится, проверь логи сервера.",
        },
      },
    },
    loadingState: {
      title: "Собираем аналитический профиль",
      description:
        "Система получает страницу, извлекает отзывы, генерирует признаки и собирает финальный скор.",
    },
    detectorGrid: {
      eyebrow: "Карточки детекторов",
      title: "Сигналы детекторов",
      description:
        "Каждая карточка переводит вывод модели и эвристик в понятный сигнал риска по товару или продавцу.",
      detectorScore: "Оценка детектора",
      status: "Статус",
    },
    explainability: {
      eyebrow: "Объяснение решения",
      title: "Почему система приняла такое решение",
      description:
        "Компактный слой объяснений для защиты, модерации и интерпретации модели. Он показывает самые сильные факторы, повлиявшие на финальный риск-профиль.",
      liveWeights: "Живые веса факторов",
      decisionNarrative: "Логика решения",
      decisionNarrativeDescription:
        "Система комбинирует текстовую схожесть, временные аномалии, смещение рейтингов, поведение авторов и языковые признаки, чтобы собрать объяснение для ручной проверки.",
      topFactors: "Топ-факторы вклада",
      topFactorsDescription:
        "Взвешенные полосы вклада показывают, какие сигналы сильнее всего повлияли на финальное решение.",
    },
    suspiciousTable: {
      eyebrow: "Таблица подозрительных отзывов",
      title: "Ранжированные примеры подозрительных отзывов",
      description:
        "Компактная таблица для ручной проверки с сортировкой, фильтрами и языковыми признаками по самым подозрительным отзывам.",
      filterPlaceholder: "Фильтр по тексту, причине, автору или языковым признакам",
      severity: {
        all: "Все уровни",
        high: "Высокий",
        medium: "Средний",
        low: "Низкий",
      },
      language: {
        all: "Все языковые профили",
        suspicious: "Подозрительный",
        mixed: "Смешанный",
        organic: "Органичный",
        neutral: "Нейтральный",
      },
      sort: {
        suspiciousness: "Сортировать по подозрительности",
        date: "Сортировать по дате",
        rating: "Сортировать по рейтингу",
      },
      triage: {
        all: "Все статусы проверки",
        confidentSuspicious: "Уверенно подозрительный",
        needsManualReview: "Нужна ручная проверка",
        confidentClean: "Уверенно чистый",
      },
      waitingTitle: "Таблица подозрительных отзывов ждет данные",
      waitingDescription:
        "Запусти детектор, чтобы открыть ранжированную таблицу с языковыми признаками, фильтрами, сортировкой и уровнями доверия к авторам.",
      emptyTitle: "По текущим фильтрам ничего не найдено",
      emptyDescription:
        "Попробуй другой поисковый запрос или ослабь фильтры по уровню риска и языковому профилю, чтобы увидеть больше отзывов.",
      summary: {
        visible: "Показано строк",
        highRisk: "Высокий риск",
        manualReview: "Нужна проверка",
        avgRisk: "Средний риск",
      },
      columns: {
        reviewText: "Текст отзыва",
        rating: "Рейтинг",
        suspiciousness: "Подозрительность",
        reason: "Причина флага",
        author: "Автор / доверие",
        date: "Дата",
      },
      labels: {
        rating: "Рейтинг",
        suspiciousness: "Подозрительность",
        reason: "Причина",
        author: "Автор",
        date: "Дата",
        templateCluster: "Шаблонный кластер",
        photoEvidence: "Фото в отзыве",
        duplicatePhotoCluster: "Кластер фото-дублей",
        photoReuse: "Повтор фото",
        photoTemporalCluster: "Временной фото-кластер",
        photoTemporalClusterScore: "Фото-бёрст",
        photoMismatch: "Фото не совпадает",
        photoTextMismatch: "Несовпадение фото/текста",
        stockMarketingPhoto: "Сток/маркетинг фото",
        stockMarketingScore: "Скор сток-фото",
        photoOcrText: "OCR-текст на фото",
        photoOcrScore: "Фото OCR",
        syntheticImageHint: "Признак синтетического изображения",
        syntheticImageScore: "Оценка синтетического изображения",
        aiTextScore: "ИИ-текст",
        slangRisk: "Языковой риск",
        grounding: "Приземленность",
        uncertainty: "Неопределенность",
        oodDrift: "OOD-дрейф",
      },
    },
    dataImport: {
      title: "Структурированные данные сайта",
      description:
        "Загрузите файл или подключите API-источник. Импортер автоматически определяет формат файла и сопоставляет колонки с полями отзывов.",
      sources: {
        file: "Файл",
        api: "API",
      },
      expectedStructure: "Ожидаемая структура",
      fetchTitle: "Загрузить по API",
      fetchDescription:
        "Укажи публичный endpoint и выполни GET-запрос. Импортер определит JSON, JSONL, CSV/TSV, Excel или HTML-ответ и нормализует его в записи отзывов.",
      fetchAction: "Загрузить данные",
      chooseFile: "Выбрать файл",
      apiPlaceholder: "https://api.example.com/reviews",
      readyTitle: "Импорт готов",
      readyDescription:
        "Структура валидна и может быть сразу отправлена в анализ структурированных данных.",
      warningTitle: "Импорт завершен с предупреждениями",
      errorTitle: "Проверка структуры не пройдена",
      errorDescription:
        "В импортированном источнике не хватает полей, обязательных для модели. Исправь структуру и повтори импорт.",
      previewTitle: "Нормализованное превью",
      previewDescription: "Первые 5-10 строк после нормализации структуры источника.",
      previewHeaders: {
        item_id: "item_id",
        user: "user",
        rating: "rating",
        timestamp: "timestamp",
        text: "text",
        ip: "ip",
        geo: "geo",
      },
      fileDrop: {
        file: "Перетащи файл сюда или кликни для загрузки",
        helper:
          "Поддерживаются Excel, CSV/TSV, JSON/JSONL и HTML. Импортер сам определит формат, покажет превью и проверит данные перед анализом.",
      },
      importLoadingTitle: "Нормализуем импортированные данные...",
      importLoadingDescription:
        "Импортер проверяет формат, извлекает записи и собирает нормализованный набор для анализа накрутки.",
      importFailedTitle: "Импорт данных не удался",
      runAnalysis: "Запустить анализ",
    },
  },
} as const;

export type AppCopy = (typeof translations)[Locale];

type LanguageContextValue = {
  copy: AppCopy;
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

function detectLocale(): Locale {
  if (typeof window === "undefined") {
    return "en";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "ru") {
    return stored;
  }

  return window.navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
}

export function getCopy(locale: Locale): AppCopy {
  return translations[locale];
}

export function LanguageProvider({ children }: PropsWithChildren) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
    window.localStorage.setItem(STORAGE_KEY, locale);
  }, [locale]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      copy: translations[locale],
      locale,
      setLocale: setLocaleState,
    }),
    [locale]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLocale() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLocale must be used within LanguageProvider.");
  }
  return context;
}
