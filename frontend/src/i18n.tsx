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
      explainabilityPreview: "Explainability preview",
      sourceLoaded: "Source loaded",
      progress: "Progress",
      complete: "complete",
    },
    hero: {
      eyebrow: "AI + ML Review Integrity System",
      title: "Detect rating manipulation and suspicious review behavior with a live analytical workspace.",
      description:
        "A premium dashboard for thesis defense and product demonstration. It combines scraping, NLP, anomaly detection, behavior signals, and moderation-oriented explainability in one unified interface.",
      primaryCta: "Check page",
      secondaryCta: "View demo",
      badges: {
        nlp: "NLP analysis",
        anomaly: "Anomaly detection",
        patterns: "Suspicious patterns",
        scraping: "Scraping + ML",
      },
      previewEyebrow: "Preview Analytics",
      previewTitle: "Live risk snapshot",
      riskScore: "Risk score",
      reviewActivity: "Review activity",
      recentCadence: "Recent cadence pattern",
      manipulationProbability: "Manipulation probability",
      confidence: "Confidence",
      flaggedReviews: "Flagged reviews",
      manualReview: "Manual review",
    },
    controlPanel: {
      eyebrow: "Main Analysis Workspace",
      title: "Control panel",
      description: "Compact controls for source selection, backend-managed collection, and analysis depth.",
      sourceSectionTitle: "Data source",
      sourceSectionHelper: "Choose how the detector should ingest the next analysis sample.",
      sourceModes: {
        url: {
          helper: "Fetch a live marketplace page through ScrapingBee.",
        },
        html: {
          helper: "Paste or upload a local snapshot for deterministic testing.",
        },
        records: {
          label: "Site Data",
          helper: "Run full rating manipulation analysis on structured records.",
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
        analysisModeHelper: "Choose how aggressive and patient the detector should be for the next run.",
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
        analyze: "Check page",
        analyzing: "Analyzing...",
        demo: "View demo",
      },
    },
    resultsPanel: {
      eyebrow: "Live Analysis Panel",
      title: "Model-driven review risk dashboard",
      description:
        "The main results workspace shows the overall risk posture, live review analytics, anomaly distributions, and suspicious evidence in one product-style monitoring view.",
      trustworthySplit: "Trustworthy / suspicious split",
      trendCharts: "Trend and anomaly charts",
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
      title: "Review intelligence pipeline",
      description:
        "A transparent view of the operational stages behind the final risk profile, from collection to final moderation-grade interpretation.",
      active: "Pipeline active",
      complete: "Pipeline complete",
      waiting: "Waiting",
    },
    emptyState: {
      title: "Ready to profile a review ecosystem",
      description:
        "Launch an analysis to populate the dashboard with a live risk profile, temporal charts, detector cards, explainability factors, and a ranked suspicious reviews table.",
      cards: [
        "Risk score and confidence",
        "Temporal and anomaly charts",
        "Detector and explainability panels",
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
        SCRAPINGBEE_NOT_CONFIGURED: {
          message:
            "ScrapingBee is not configured on the backend. Set `SCRAPINGBEE_API_KEY` in `.env` or the process environment.",
          helper: "Restart Flask after changing backend environment variables, then retry the request.",
        },
        SCRAPING_FETCH_FAILED: {
          message: "ScrapingBee could not fetch the marketplace page.",
          helper: "Try HTML snapshot mode, reduce the analysis depth, or check ScrapingBee credits/proxy availability.",
        },
        SCRAPING_TIMEOUT: {
          message: "ScrapingBee did not return the page before the backend timeout.",
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
      title: "Fraud detector surface",
      description:
        "Each detector card translates raw model and heuristic behavior into a moderation-friendly, product-level signal.",
      detectorScore: "Detector score",
      status: "Status",
    },
    explainability: {
      eyebrow: "Explainability",
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
      title: "Ranked suspicious review evidence",
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
        slangRisk: "Slang risk",
        grounding: "Grounding",
        uncertainty: "Uncertainty",
        oodDrift: "OOD drift",
      },
    },
    dataImport: {
      title: "Structured site data",
      description:
        "One import workspace for structured payloads, files, and API responses before running the rating manipulation detector.",
      expectedStructure: "Expected structure",
      fetchTitle: "Fetch from an API",
      fetchDescription:
        "Enter a public endpoint and run a GET request. The importer will try to normalize JSON, CSV, Excel, or HTML responses into site-data records.",
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
        json: "Drop a JSON file here or click to upload",
        csv: "Drop a CSV file here or click to upload",
        excel: "Drop an Excel file here or click to upload",
        html: "Drop an HTML file here or click to upload",
        helper:
          "files are supported here. After upload, the importer will show a preview and validate the structure before analysis starts.",
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
      explainabilityPreview: "Превью explainability",
      sourceLoaded: "Источник загружен",
      progress: "Прогресс",
      complete: "завершено",
    },
    hero: {
      eyebrow: "AI + ML система проверки отзывов",
      title: "Выявляйте накрутку рейтингов и подозрительное поведение в отзывах в живом аналитическом workspace.",
      description:
        "Премиальный дашборд для защиты диплома и продуктовой демонстрации. Он объединяет scraping, NLP, поиск аномалий, поведенческие сигналы и explainability для модерации в одном интерфейсе.",
      primaryCta: "Проверить страницу",
      secondaryCta: "Открыть демо",
      badges: {
        nlp: "NLP-анализ",
        anomaly: "Поиск аномалий",
        patterns: "Подозрительные паттерны",
        scraping: "Scraping + ML",
      },
      previewEyebrow: "Предпросмотр аналитики",
      previewTitle: "Живой снимок риска",
      riskScore: "Риск-скор",
      reviewActivity: "Активность отзывов",
      recentCadence: "Недавний паттерн публикаций",
      manipulationProbability: "Вероятность накрутки",
      confidence: "Уверенность",
      flaggedReviews: "Подозрительные отзывы",
      manualReview: "Ручная проверка",
    },
    controlPanel: {
      eyebrow: "Основной workspace анализа",
      title: "Панель управления",
      description: "Компактные настройки источника, backend-сбора и глубины анализа.",
      sourceSectionTitle: "Источник данных",
      sourceSectionHelper: "Выберите, как детектор должен получить следующий образец для анализа.",
      sourceModes: {
        url: {
          helper: "Забирает живую страницу маркетплейса через ScrapingBee.",
        },
        html: {
          helper: "Вставьте или загрузите локальный snapshot для детерминированной проверки.",
        },
        records: {
          label: "Данные сайта",
          helper: "Запускает полный анализ накрутки рейтингов на структурированных данных.",
        },
      },
      fields: {
        productPageUrl: "URL страницы товара",
        productPageUrlHelper: "Лучше всего работает, когда блоки отзывов доступны на полученной странице.",
        sourceLabel: "Метка источника",
        sourceLabelHelper: "Необязательная метка или канонический URL для snapshot.",
        htmlSource: "HTML-источник",
        htmlSourceHelper: "Вставьте сырой HTML из сохраненного snapshot страницы.",
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
        analyze: "Проверить страницу",
        analyzing: "Идет анализ...",
        demo: "Открыть демо",
      },
    },
    resultsPanel: {
      eyebrow: "Панель живого анализа",
      title: "Риск-дашборд на основе модели",
      description:
        "Основной workspace результатов показывает общий риск-профиль, живую аналитику по отзывам, распределения аномалий и подозрительные evidence в одном monitoring-view.",
      trustworthySplit: "Надежные / подозрительные",
      trendCharts: "Графики трендов и аномалий",
      unexpectedFailure: "Непредвиденный сбой анализа.",
    },
    resultsSuccess: {
      riskProfile: "Риск-профиль",
      riskScore: "Риск-скор",
      manipulationProbability: "Вероятность накрутки",
      confidence: "Уверенность",
      collectedReviews: "Собрано отзывов",
      flaggedReviews: "Выявлено отзывов",
      manualReview: "Ручная проверка",
      explainabilityEyebrow: "Сводка explainability",
      explainabilityTitle: "Почему был назначен этот риск-профиль",
      explainabilityDescription:
        "Короткий decision digest, который показывает самые сильные сигналы уровня продукта до погружения в детальную explainability-секцию ниже.",
      decisionDigest: "Decision digest",
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
      eyebrow: "Пайплайн",
      title: "Пайплайн review intelligence",
      description:
        "Прозрачный вид на операционные этапы, стоящие за финальным риск-профилем: от сбора данных до итоговой moderation-grade интерпретации.",
      active: "Пайплайн активен",
      complete: "Пайплайн завершен",
      waiting: "Ожидание",
    },
    emptyState: {
      title: "Все готово для профилирования экосистемы отзывов",
      description:
        "Запусти анализ, чтобы заполнить дашборд живым риск-профилем, временными графиками, карточками детекторов, explainability-факторами и ранжированной таблицей подозрительных отзывов.",
      cards: [
        "Риск-скор и уверенность",
        "Временные графики и аномалии",
        "Панели детекторов и explainability",
      ],
    },
    errorState: {
      title: "Анализ не удалось завершить",
      helper: "Проверь URL страницы или загруженные данные отзывов, а затем повтори запрос.",
      errors: {
        ANALYSIS_FAILED: {
          message: "Backend не смог завершить анализ.",
          helper: "Проверь backend-логи, устрани причину и повтори запрос.",
        },
        INPUT_SOURCE_MISSING: {
          message: "Источник для анализа не передан.",
          helper: "Выбери URL, HTML или Site Data и заполни нужные данные.",
        },
        INVALID_INPUT: {
          message: "Backend отклонил переданные данные.",
          helper: "Проверь введённые данные и повтори запрос.",
        },
        INVALID_RESPONSE: {
          message: "Backend вернул некорректный ответ.",
          helper: "Обнови страницу и повтори запрос. Если ошибка повторится, проверь API-логи.",
        },
        INVALID_URL: {
          message: "URL страницы товара некорректен.",
          helper: "Используй полный URL, который начинается с http:// или https://.",
        },
        INVALID_SCRAPING_WAIT: {
          message: "Ручное ожидание слишком большое для scraping-timeout.",
          helper: "Поставь 0-30000 мс или очисти поле, чтобы режим анализа сам выбрал безопасное значение.",
        },
        NETWORK_ERROR: {
          message: "Frontend не смог подключиться к backend анализа.",
          helper: "Убедись, что Flask запущен на порту 5000, затем повтори запрос.",
        },
        RATING_ARTIFACTS_MISSING: {
          message: "Артефакты rating anti-fraud модели отсутствуют.",
          helper: "Запусти обучение rating-модели перед режимом Site Data.",
        },
        REQUEST_BODY_INVALID: {
          message: "Тело API-запроса некорректно.",
          helper: "Обнови страницу и повтори запрос.",
        },
        REVIEW_ARTIFACTS_MISSING: {
          message: "Артефакты review-модели отсутствуют.",
          helper: "Запусти обучение review-модели перед анализом страниц.",
        },
        SCRAPINGBEE_NOT_CONFIGURED: {
          message:
            "ScrapingBee не настроен на backend. Укажи `SCRAPINGBEE_API_KEY` в `.env` или переменных окружения процесса.",
          helper: "После изменения backend-переменных перезапусти Flask, затем повтори запрос.",
        },
        SCRAPING_FETCH_FAILED: {
          message: "ScrapingBee не смог получить страницу маркетплейса.",
          helper: "Попробуй HTML snapshot mode, уменьши глубину анализа или проверь credits/proxy в ScrapingBee.",
        },
        SCRAPING_TIMEOUT: {
          message: "ScrapingBee не вернул страницу до backend-timeout.",
          helper: "Уменьши ручное ожидание, используй Быстро/Стандарт или вставь HTML snapshot для стабильной проверки.",
        },
        UNKNOWN_ERROR: {
          message: "Произошла непредвиденная ошибка анализа.",
          helper: "Повтори запрос. Если ошибка повторится, проверь backend-логи.",
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
      title: "Поверхность fraud-детекторов",
      description:
        "Каждая карточка переводит сырое поведение модели и эвристик в удобный для модерации сигнал уровня продукта.",
      detectorScore: "Скор детектора",
      status: "Статус",
    },
    explainability: {
      eyebrow: "Explainability",
      title: "Почему система приняла такое решение",
      description:
        "Компактный слой объяснений для защиты, модерации и интерпретации модели. Он показывает самые сильные факторы, повлиявшие на финальный риск-профиль.",
      liveWeights: "Живые веса факторов",
      decisionNarrative: "Нарратив решения",
      decisionNarrativeDescription:
        "Система комбинирует текстовую схожесть, временные аномалии, смещение рейтингов, поведение авторов и bilingual slang cues, чтобы собрать ориентированное на модерацию объяснение.",
      topFactors: "Топ-факторы вклада",
      topFactorsDescription:
        "Взвешенные contribution-бары показывают, какие сигналы сильнее всего доминировали в финальном решении.",
    },
    suspiciousTable: {
      eyebrow: "Таблица подозрительных отзывов",
      title: "Ранжированные evidence по подозрительным отзывам",
      description:
        "Компактная таблица для модерации с сортировкой, фильтрами и языковыми evidence по самым подозрительным отзывам.",
      filterPlaceholder: "Фильтр по тексту, причине, автору или slang-терминам",
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
        all: "Все triage-статусы",
        confidentSuspicious: "Уверенно подозрительный",
        needsManualReview: "Нужна ручная проверка",
        confidentClean: "Уверенно чистый",
      },
      waitingTitle: "Таблица подозрительных отзывов ждет данные",
      waitingDescription:
        "Запусти детектор, чтобы открыть ранжированную таблицу с языковыми evidence, фильтрами, сортировкой и уровнями доверия к авторам.",
      emptyTitle: "По текущим фильтрам ничего не найдено",
      emptyDescription:
        "Попробуй другой поисковый запрос или ослабь фильтры по severity и language profile, чтобы увидеть больше отзывов.",
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
        syntheticImageHint: "AI/synthetic hint",
        syntheticImageScore: "AI-image подсказка",
        slangRisk: "Slang-риск",
        grounding: "Приземленность",
        uncertainty: "Неопределенность",
        oodDrift: "OOD-дрейф",
      },
    },
    dataImport: {
      title: "Структурированные данные сайта",
      description:
        "Единый workspace импорта для структурированных payload, файлов и API-ответов перед запуском детектора накрутки рейтингов.",
      expectedStructure: "Ожидаемая структура",
      fetchTitle: "Загрузить из API",
      fetchDescription:
        "Укажи публичный endpoint и выполни GET-запрос. Импортер попытается нормализовать JSON, CSV, Excel или HTML-ответы в site-data records.",
      fetchAction: "Загрузить данные",
      chooseFile: "Выбрать файл",
      apiPlaceholder: "https://api.example.com/reviews",
      readyTitle: "Импорт готов",
      readyDescription:
        "Структура валидна и может быть сразу отправлена в пайплайн анализа site-data.",
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
        json: "Перетащи JSON-файл сюда или кликни для загрузки",
        csv: "Перетащи CSV-файл сюда или кликни для загрузки",
        excel: "Перетащи Excel-файл сюда или кликни для загрузки",
        html: "Перетащи HTML-файл сюда или кликни для загрузки",
        helper:
          "файлы поддерживаются здесь. После загрузки импортер покажет превью и провалидирует структуру до старта анализа.",
      },
      importLoadingTitle: "Нормализуем импортированные данные...",
      importLoadingDescription:
        "Импортер проверяет формат, извлекает записи и собирает нормализованный payload для антифрод-пайплайна.",
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
