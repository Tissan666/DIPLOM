import { getDemoResult } from "./mockData";
import type { Locale } from "../i18n";
import type {
  AnomalyTypePoint,
  DashboardResult,
  DetectorCardData,
  ExplainabilityFactor,
  ReviewApiResponse,
  ReviewTriageStatus,
  SourceMode,
  SuspiciousReviewRow,
} from "../types/analysis";

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function groupCounts(labels: string[]) {
  const counts = new Map<string, number>();
  labels.forEach((label) => {
    counts.set(label, (counts.get(label) || 0) + 1);
  });
  return Array.from(counts.entries()).map(([label, count]) => ({ label, count }));
}

function severityFromScore(score: number): "low" | "medium" | "high" {
  if (score >= 72) {
    return "high";
  }
  if (score >= 48) {
    return "medium";
  }
  return "low";
}

function detectorStatusFromScore(score: number): "stable" | "watch" | "critical" {
  if (score >= 72) {
    return "critical";
  }
  if (score >= 48) {
    return "watch";
  }
  return "stable";
}

function trustLevel(probability: number): "trusted" | "neutral" | "low" {
  if (probability >= 0.8) {
    return "low";
  }
  if (probability >= 0.55) {
    return "neutral";
  }
  return "trusted";
}

const knownTextTranslations: Record<string, string> = {
  "Text similarity": "Текстовая схожесть",
  "Burst posting": "Всплеск публикаций",
  "Temporal cluster": "Временной кластер",
  "Bilingual slang signal": "Сигнал bilingual slang",
  "Rating shift": "Сдвиг рейтингов",
  "Sentiment repetition": "Повтор sentiment-паттернов",
  "User cluster anomaly": "Аномалия user-кластера",
  "Threshold breach": "Пороговое срабатывание",
  "Repeated suspicious users": "Повторяющиеся подозрительные пользователи",
  "Autoencoder anomaly score": "Аномальный скор автоэнкодера",
  "Suspicious review ratio": "Доля подозрительных отзывов",
  "Behavioral manipulation score": "Поведенческий скор манипуляции",
  "Peak suspicious probability": "Пиковая вероятность подозрительности",
  "Manual review uncertainty": "Неопределенность ручной проверки",
  "Photo forensics signal": "Фото-форензика",
  "Low-risk review profile": "Низкорисковый профиль отзывов",
  "Extraction coverage": "Покрытие извлечения отзывов",
  "The neural model considers this review highly suspicious.": "Нейросетевая модель считает этот отзыв сильно подозрительным.",
  "The review has several linguistic patterns often seen in manipulated feedback.": "В отзыве есть несколько языковых паттернов, которые часто встречаются в накрученной обратной связи.",
  "The review is unusually short and provides very little concrete detail.": "Отзыв необычно короткий и почти не содержит конкретных деталей.",
  "The text relies on heavy emotional punctuation.": "Текст опирается на чрезмерно эмоциональную пунктуацию.",
  "The wording looks promotional or strongly templated.": "Формулировки выглядят рекламно или слишком шаблонно.",
  "There is visible repetition, which can indicate scripted review text.": "В тексте заметны повторы, что может указывать на заранее подготовленный отзыв.",
  "An extreme rating is paired with a generic explanation.": "Экстремальная оценка сочетается со слишком общей аргументацией.",
  "The wording resembles promotional or templated review language.": "Формулировки похожи на рекламный или шаблонный язык отзывов.",
  "The model routed this review to manual moderation.": "Модель отправила этот отзыв на ручную модерацию.",
  "Hybrid detector considered this review unusual.": "Гибридный детектор посчитал этот отзыв нетипичным.",
  "Behavioral autoencoder marked this record as anomalous.": "Поведенческий автоэнкодер отметил эту запись как аномальную.",
  "No reviews were available for scoring.": "Нет отзывов, доступных для скоринга.",
  "The model did not flag any extracted reviews as suspicious.": "Модель не отметила извлечённые отзывы как подозрительные.",
  "Suspicious reviews are ranked by a calibrated hybrid score that combines the neural text model and manipulation signals.": "Подозрительные отзывы ранжируются калиброванным гибридным скором, который объединяет нейросетевую текстовую модель и сигналы манипуляции.",
  "Behavioral and statistical page signals also suggest possible rating manipulation.": "Поведенческие и статистические сигналы страницы также указывают на возможную накрутку рейтинга.",
  "The same or nearly identical review text appears multiple times on this page.": "Одинаковый или почти одинаковый текст отзыва встречается на странице несколько раз.",
  "The review title repeats across multiple ratings.": "Заголовок отзыва повторяется в нескольких оценках.",
  "The same author appears unusually often in the current review sample.": "Один и тот же автор необычно часто встречается в текущей выборке отзывов.",
  "Many reviews were published in a tight date cluster.": "Много отзывов опубликовано в плотном временном кластере.",
  "The date cluster is dominated by extreme ratings.": "Во временном кластере преобладают экстремальные оценки.",
  "An extreme rating is paired with a very short explanation.": "Экстремальная оценка сочетается с очень коротким объяснением.",
  "The page is dominated by extreme ratings, which may indicate manipulation.": "На странице преобладают экстремальные оценки, что может указывать на манипуляцию.",
  "A noticeable share of the page contains duplicated review content.": "Заметная часть страницы содержит дублирующийся текст отзывов.",
  "A large portion of the reviews appeared on the same day.": "Большая часть отзывов появилась в один день.",
  "A small set of authors contributes a disproportionate share of reviews.": "Небольшая группа авторов оставила непропорционально большую долю отзывов.",
  "Many comments rely on hype-heavy slang instead of grounded product detail.": "Многие комментарии опираются на хайповый сленг вместо конкретных деталей о товаре.",
  "Russian and English slang are mixed unusually often across the current review page.": "Русский и английский сленг необычно часто смешиваются на текущей странице отзывов.",
  "Russian and English slang are mixed unusually often across the current review sample.": "Русский и английский сленг необычно часто смешиваются в текущей выборке отзывов.",
  "A repeated slang template appears across multiple reviews on the page.": "Повторяющийся slang-шаблон встречается в нескольких отзывах на странице.",
  "A repeated slang template appears across multiple reviews, which strengthens the coordination hypothesis.": "Повторяющийся slang-шаблон встречается в нескольких отзывах, что усиливает гипотезу координации.",
  "A similar slang-heavy template repeats across multiple ratings.": "Похожий slang-шаблон повторяется в нескольких оценках.",
  "A similar slang signature appears across multiple reviews, which looks coordinated.": "Похожий slang-сигнатурный паттерн встречается в нескольких отзывах и выглядит скоординированным.",
  "Several comments use grounded colloquial language with concrete detail, which slightly weakens the fake-review hypothesis.": "Несколько комментариев используют живую разговорную речь с конкретными деталями, что немного ослабляет гипотезу фейковых отзывов.",
  "The bilingual slang detector found a visible share of hype-heavy comments that look more coordinated than conversational.": "Bilingual slang-детектор нашёл заметную долю хайповых комментариев, которые выглядят скорее скоординированными, чем естественными.",
  "The slang detector also uses validation-calibrated weights and marketplace-aware lexicons, not only hand-written rules.": "Slang-детектор использует не только ручные правила, но и веса, откалиброванные на validation-наборе, а также marketplace-aware лексиконы.",
  "The same slang-heavy language pattern appears in multiple reviews on this page.": "Одинаковый slang-паттерн встречается в нескольких отзывах на этой странице.",
  "The language pattern looks hype-heavy and weakly grounded in real usage detail.": "Языковой паттерн выглядит хайповым и слабо привязанным к реальным деталям использования.",
  "The review mixes Russian and English hype slang in a way that looks orchestrated rather than natural.": "Отзыв смешивает русский и английский hype-slang так, что это выглядит скорее срежиссированно, чем естественно.",
  "The slang pattern looks unusually hype-driven for a natural customer comment.": "Slang-паттерн выглядит слишком hype-driven для естественного покупательского комментария.",
  "The hybrid score falls inside the manual-review band.": "Гибридный скор попал в зону ручной проверки.",
  "The model signals disagree too much for an automated decision.": "Сигналы модели слишком сильно расходятся для автоматического решения.",
  "The review looks out-of-domain relative to the training corpus.": "Отзыв выглядит вне домена относительно обучающего корпуса.",
  "Too little of the wording matches patterns seen during training.": "Слишком малая часть формулировок совпадает с паттернами, встречавшимися при обучении.",
  "The raw text model and the hybrid fraud model disagree materially.": "Сырая текстовая модель и гибридная fraud-модель существенно расходятся.",
  "The same IP address is associated with many accounts.": "Один и тот же IP-адрес связан со многими аккаунтами.",
  "The rating happened in an unusual short-term burst.": "Оценка появилась в необычном краткосрочном всплеске активности.",
  "The user posted several ratings in a short period.": "Пользователь оставил несколько оценок за короткий период.",
  "The review text is duplicated across several ratings.": "Текст отзыва дублируется в нескольких оценках.",
  "The rating strongly deviates from the normal score for this item.": "Оценка сильно отклоняется от обычного рейтинга этого товара.",
  "The score is statistically unusual compared with other ratings for this item.": "Оценка статистически нетипична по сравнению с другими оценками этого товара.",
  "The rating is extreme and paired with a very short review.": "Экстремальная оценка сопровождается очень коротким отзывом.",
  "The wording uses promotional stock phrases that often appear in coordinated ratings.": "Формулировка использует рекламные шаблонные фразы, которые часто встречаются в скоординированных оценках.",
  "OCR found sale, discount, coupon, promo, or similar marketing text on the photo.": "OCR нашёл на фото sale, discount, coupon, promo или похожий маркетинговый текст.",
  "OCR found hype claims such as best product, best seller, top choice, or must buy.": "OCR нашёл хайповые заявления вроде best product, best seller, top choice или must buy.",
  "OCR found ad, sponsored, official-store, or watermark-style text on the photo.": "OCR нашёл на фото текст в стиле рекламы, sponsored, official-store или watermark.",
  "OCR found contact handles, social links, or store/domain text on the photo.": "OCR нашёл на фото контакты, социальные ссылки или текст магазина/домена.",
  "Customer photos were extracted, but CLIP/ViT image-text alignment is not configured on this machine yet.": "Покупательские фото были извлечены, но CLIP/ViT-сопоставление изображения и текста на этой машине ещё не настроено.",
  "The customer photo evidence is reused across multiple reviews.": "Покупательское фото повторяется в нескольких отзывах.",
  "The same customer photo appears in a short time window across different authors.": "Одно и то же покупательское фото появилось у разных авторов за короткий промежуток времени.",
  "The attached customer photo does not match the review text or inferred product category.": "Прикрепленное фото не совпадает с текстом отзыва или предполагаемой категорией товара.",
  "The customer image looks like a stock, catalog, studio, render, banner, or listing asset.": "Фото выглядит как стоковый, каталожный, студийный, рендерный, баннерный или listing-ассет.",
  "The image has weak AI-generated or synthetic-image indicators; treat this as supporting evidence, not proof.": "У изображения есть слабые признаки AI-generated/synthetic; это только вспомогательный сигнал, не доказательство.",
  "OCR found promo, watermark, contact, marketplace, or sales text on the customer photo.": "OCR нашёл на фото промо-текст, watermark, контакты, marketplace branding или sales-надписи.",
};

function localizeKnownText(text: string, locale: Locale) {
  if (locale === "en") {
    return text;
  }
  const dynamicTranslation = localizeDynamicKnownText(text);
  if (dynamicTranslation) {
    return dynamicTranslation;
  }
  return knownTextTranslations[text] || text;
}

function localizeDynamicKnownText(text: string) {
  const manualReviewMatch = text.match(
    /^(\d+) review\(s\) were routed to manual review because the model saw uncertainty or out-of-domain patterns\.$/
  );
  if (manualReviewMatch) {
    return `${manualReviewMatch[1]} отзыв(ов) отправлены на ручную проверку из-за неопределённости или out-of-domain паттернов.`;
  }

  const duplicatePhotoMatch = text.match(
    /^Customer photo reuse was detected in (\d+) review\(s\); the largest shared-photo cluster spans (\d+) reviews\.$/
  );
  if (duplicatePhotoMatch) {
    return `Повтор покупательских фото найден в ${duplicatePhotoMatch[1]} отзыв(ах); крупнейший shared-photo кластер охватывает ${duplicatePhotoMatch[2]} отзыв(ов).`;
  }

  const temporalPhotoMatch = text.match(
    /^Coordinated photo timing was detected in (\d+) review\(s\): the same customer image appeared across different authors inside a ([\d.]+)-hour window\.$/
  );
  if (temporalPhotoMatch) {
    return `Скоординированное время появления фото найдено в ${temporalPhotoMatch[1]} отзыв(ах): одно и то же покупательское изображение появилось у разных авторов в пределах ${temporalPhotoMatch[2]} часов.`;
  }

  const imageMismatchMatch = text.match(
    /^Image-text alignment flagged (\d+) customer photo\(s\) as visually inconsistent with the review text or inferred product category\.$/
  );
  if (imageMismatchMatch) {
    return `Image-text alignment отметил ${imageMismatchMatch[1]} покупательских фото как визуально несогласованные с текстом отзыва или предполагаемой категорией товара.`;
  }

  const stockPhotoMatch = text.match(
    /^Stock\/marketing photo detection flagged (\d+) image\(s\) that look closer to catalog, studio, render, banner, or listing assets than user-taken snapshots\.$/
  );
  if (stockPhotoMatch) {
    return `Детектор stock/marketing фото отметил ${stockPhotoMatch[1]} изображений, похожих скорее на каталог, студийный рендер, баннер или listing-ассет, чем на пользовательское фото.`;
  }

  const syntheticMatch = text.match(
    /^AI\/synthetic image detection produced weak auxiliary hints on (\d+) image\(s\); this signal should support, not replace, human review or stronger fraud evidence\.$/
  );
  if (syntheticMatch) {
    return `AI/synthetic image detector дал слабые вспомогательные сигналы по ${syntheticMatch[1]} изображению(ям); этот сигнал должен дополнять, а не заменять ручную проверку или более сильные fraud-доказательства.`;
  }

  const ocrMatch = text.match(
    /^OCR found promo text, watermark-like text, contact handles, or marketplace branding on (\d+) customer photo\(s\)\.$/
  );
  if (ocrMatch) {
    return `OCR нашёл promo-текст, watermark-подобный текст, контакты или marketplace branding на ${ocrMatch[1]} покупательских фото.`;
  }

  const topAuthorMatch = text.match(/^Top suspicious author cluster: (.+) with (\d+) flagged review\(s\)\.$/);
  if (topAuthorMatch) {
    return `Главный подозрительный кластер авторов: ${topAuthorMatch[1]}, ${topAuthorMatch[2]} отмеченных отзыв(ов).`;
  }

  const groundingMatch = text.match(/^Language grounding was calibrated against the inferred (.+) product domain\.$/);
  if (groundingMatch) {
    return `Language grounding откалиброван относительно предполагаемого домена товара: ${groundingMatch[1]}.`;
  }

  const slangTermsMatch = text.match(
    /^The slang profile looks hype-heavy and weakly grounded in (.+) detail \((.+)\)\.$/
  );
  if (slangTermsMatch) {
    return `Slang-профиль выглядит хайповым и слабо привязанным к деталям домена ${slangTermsMatch[1]} (${slangTermsMatch[2]}).`;
  }

  const slangDomainMatch = text.match(/^The slang profile looks hype-heavy and weakly grounded in (.+) detail\.$/);
  if (slangDomainMatch) {
    return `Slang-профиль выглядит хайповым и слабо привязанным к деталям домена ${slangDomainMatch[1]}.`;
  }

  const duplicatePhotoLargeMatch = text.match(
    /^The same customer photo appears across a large cluster of (\d+) reviews\.$/
  );
  if (duplicatePhotoLargeMatch) {
    return `Одно и то же покупательское фото встречается в большом кластере из ${duplicatePhotoLargeMatch[1]} отзывов.`;
  }

  const duplicatePhotoCountMatch = text.match(/^The same customer photo appears in (\d+) reviews\.$/);
  if (duplicatePhotoCountMatch) {
    return `Одно и то же покупательское фото встречается в ${duplicatePhotoCountMatch[1]} отзывах.`;
  }

  const temporalClusterMatch = text.match(
    /^The same customer photo appears across (\d+) reviews by (\d+) authors within ([\d.]+) hours\.$/
  );
  if (temporalClusterMatch) {
    return `Одно и то же покупательское фото встречается в ${temporalClusterMatch[1]} отзывах от ${temporalClusterMatch[2]} авторов за ${temporalClusterMatch[3]} часов.`;
  }

  const temporalShortWindowMatch = text.match(
    /^The same customer photo appears across different authors within a short ([\d.]+)-hour window\.$/
  );
  if (temporalShortWindowMatch) {
    return `Одно и то же покупательское фото встречается у разных авторов в коротком окне ${temporalShortWindowMatch[1]} часов.`;
  }

  const photoMismatchDetailMatch = text.match(
    /^The customer photo looks closer to (.+) than to the review text or inferred (.+) category\.$/
  );
  if (photoMismatchDetailMatch) {
    return `Покупательское фото больше похоже на ${photoMismatchDetailMatch[1]}, чем на текст отзыва или предполагаемую категорию ${photoMismatchDetailMatch[2]}.`;
  }

  const stockMarketingDetailMatch = text.match(
    /^The customer image looks like (.+), not a user-taken product photo\.$/
  );
  if (stockMarketingDetailMatch) {
    return `Покупательское изображение похоже на ${stockMarketingDetailMatch[1]}, а не на пользовательское фото товара.`;
  }

  const syntheticDetailMatch = text.match(
    /^Weak auxiliary signal: the image shows (.+)\. Treat this as supporting evidence, not proof\.$/
  );
  if (syntheticDetailMatch) {
    return `Слабый вспомогательный сигнал: изображение показывает ${syntheticDetailMatch[1]}. Это дополнительный сигнал, а не доказательство.`;
  }

  const suspiciousWordingMatch = text.match(
    /^The wording matches suspicious slang terms: (.+)\.$/
  );
  if (suspiciousWordingMatch) {
    return `Формулировка совпадает с подозрительными slang-терминами: ${suspiciousWordingMatch[1]}.`;
  }

  const slangToneMatch = text.match(
    /^The slang-heavy tone contains little concrete (.+) detail\.$/
  );
  if (slangToneMatch) {
    return `Slang-heavy тон содержит мало конкретных деталей домена ${slangToneMatch[1]}.`;
  }

  const learnedMarketplaceSlangMatch = text.match(
    /^The wording matches suspicious slang patterns learned from (.+)-style reviews\.$/
  );
  if (learnedMarketplaceSlangMatch) {
    return `Формулировка совпадает с подозрительными slang-паттернами, выученными на отзывах в стиле ${learnedMarketplaceSlangMatch[1]}.`;
  }

  const marketplaceHypeSlangMatch = text.match(
    /^The comment uses hype-heavy (.+)-style slang but gives little grounded delivery or product detail\.$/
  );
  if (marketplaceHypeSlangMatch) {
    return `Комментарий использует hype-heavy slang в стиле ${marketplaceHypeSlangMatch[1]}, но даёт мало конкретики о доставке или товаре.`;
  }

  const domainSpecificSlangMatch = text.match(
    /^The slang-heavy tone contains little (.+)-specific detail, which can indicate scripted hype\.$/
  );
  if (domainSpecificSlangMatch) {
    return `Slang-heavy тон содержит мало деталей, специфичных для ${domainSpecificSlangMatch[1]}, что может указывать на scripted hype.`;
  }

  const ocrForeignMarketplaceMatch = text.match(
    /^OCR found marketplace text that does not match the source site: (.+)\.$/
  );
  if (ocrForeignMarketplaceMatch) {
    return `OCR нашёл marketplace-текст, который не совпадает с исходным сайтом: ${ocrForeignMarketplaceMatch[1]}.`;
  }

  const ocrMarketplaceBrandMatch = text.match(/^OCR found marketplace branding text on the photo: (.+)\.$/);
  if (ocrMarketplaceBrandMatch) {
    return `OCR нашёл marketplace branding на фото: ${ocrMarketplaceBrandMatch[1]}.`;
  }

  return "";
}

function triageSeverity(
  status: ReviewTriageStatus,
  suspiciousness: number,
  uncertaintyScore: number
): "low" | "medium" | "high" {
  if (status === "confident_suspicious") {
    return severityFromScore(suspiciousness * 100);
  }
  if (status === "needs_manual_review") {
    return uncertaintyScore >= 0.55 ? "high" : "medium";
  }
  return "low";
}

function authorTrustFromTriage(
  status: ReviewTriageStatus,
  probability: number
): "trusted" | "neutral" | "low" {
  if (status === "confident_suspicious") {
    return "low";
  }
  if (status === "needs_manual_review") {
    return "neutral";
  }
  return trustLevel(probability);
}

function buildExplainability(topReasons: Array<{ type: string; count: number }>, locale: Locale): ExplainabilityFactor[] {
  const total = topReasons.reduce((sum, item) => sum + item.count, 0) || 1;
  return topReasons.slice(0, 5).map((reason) => ({
    label: localizeKnownText(reason.type, locale),
    weight: reason.count / total,
    narrative:
      locale === "ru"
        ? `Этот сигнал дал около ${Math.round((reason.count / total) * 100)}% видимой explainability-массы в текущей выборке отзывов.`
        : `This signal contributed ${Math.round((reason.count / total) * 100)}% of the visible explanation mass in the current review sample.`,
  }));
}

function humanizeDomainLabel(domain: string, locale: Locale) {
  if (!domain || domain === "general") {
    return locale === "ru" ? "общий" : "general";
  }

  const normalized = domain.replace(/-/g, " ");
  if (locale === "en") {
    return normalized;
  }

  const map: Record<string, string> = {
    apparel: "одежда",
    beauty: "красота",
    electronics: "электроника",
    grocery: "продукты",
    "home goods": "товары для дома",
    general: "общий",
  };

  return map[normalized] || normalized;
}

function buildSlangDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const slangManipulationMean = Number(summary.slang_manipulation_mean || 0);
  const slangAuthenticityMean = Number(summary.slang_authenticity_mean || 0.5);
  const pageSlangSignalRatio = Number(summary.page_slang_signal_ratio || 0);
  const pageBilingualSlangRatio = Number(summary.page_bilingual_slang_ratio || 0);
  const pageOrganicSlangRatio = Number(summary.page_organic_slang_ratio || 0);
  const templateClusterRatio = Number(summary.slang_template_cluster_ratio || 0);
  const domainLabel = humanizeDomainLabel(String(summary.slang_domain_label || "general"), locale);

  const score = Math.round(
    clamp(
      (
        slangManipulationMean * 0.48 +
        pageSlangSignalRatio * 0.24 +
        pageBilingualSlangRatio * 0.18 +
        templateClusterRatio * 0.16 +
        Math.max(0, 0.6 - slangAuthenticityMean) * 0.18 -
        pageOrganicSlangRatio * 0.08
      ) * 100,
      4,
      96
    )
  );

  return {
    id: "bilingual-slang",
    name: locale === "ru" ? "Проверка bilingual slang" : "Bilingual Slang Check",
    description:
      locale === "ru"
        ? domainLabel === "общий"
          ? "Отделяет органичный разговорный RU/EN-язык от hype-heavy mixed slang и scripted promo-tone."
          : `Отделяет органичный разговорный RU/EN-язык от hype-heavy mixed slang, используя grounding-сигналы домена ${domainLabel}.`
        : domainLabel === "general"
          ? "Separates organic RU/EN colloquial language from hype-heavy mixed slang and scripted promo tone."
          : `Separates organic RU/EN colloquial language from hype-heavy mixed slang using ${domainLabel}-specific grounding cues.`,
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildSlangInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const totalReviews = Number(summary.total_reviews || 0);
  const slangManipulationMean = Number(summary.slang_manipulation_mean || 0);
  const slangAuthenticityMean = Number(summary.slang_authenticity_mean || 0.5);
  const pageSlangSignalRatio = Number(summary.page_slang_signal_ratio || 0);
  const pageBilingualSlangRatio = Number(summary.page_bilingual_slang_ratio || 0);
  const pageOrganicSlangRatio = Number(summary.page_organic_slang_ratio || 0);
  const templateClusterRatio = Number(summary.slang_template_cluster_ratio || 0);
  const domainLabel = humanizeDomainLabel(String(summary.slang_domain_label || "general"), locale);

  if (totalReviews > 0 && totalReviews < 4) {
    return null;
  }

  if (templateClusterRatio >= 0.18) {
    return locale === "ru"
      ? `Slang-движок нашел повторяющиеся языковые шаблоны примерно в ${Math.round(templateClusterRatio * 100)}% текущей выборки.`
      : `The slang engine found repeated language templates across ${Math.round(templateClusterRatio * 100)}% of the current sample.`;
  }
  if (pageSlangSignalRatio >= 0.25 || slangManipulationMean >= 0.22) {
    return locale === "ru"
      ? `Bilingual slang-анализ пометил около ${Math.round(pageSlangSignalRatio * 100)}% выборки как hype-heavy или слабо grounded ${domainLabel}-язык.`
      : `Bilingual slang analysis flagged ${Math.round(pageSlangSignalRatio * 100)}% of the sample for hype-heavy or weakly grounded ${domainLabel} language.`;
  }
  if (pageBilingualSlangRatio >= 0.18) {
    return locale === "ru"
      ? "Русский и английский slang смешиваются в этой выборке необычно часто, что повышает риск координации."
      : "Russian and English slang are mixed unusually often in this review sample, which raises coordination risk.";
  }
  if (pageOrganicSlangRatio >= 0.25 && slangAuthenticityMean >= 0.58) {
    return locale === "ru"
      ? "Slang-layer видит в основном grounded conversational language, а не scripted hype, что немного ослабляет fraud-гипотезу."
      : "The slang layer sees mostly grounded conversational language rather than scripted hype, which softens the fraud hypothesis.";
  }
  return null;
}

function buildPhotoForensicsInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const duplicatePhotoReviews = Number(summary.duplicate_photo_reviews || 0);
  const largestCluster = Number(summary.largest_duplicate_photo_cluster || 0);
  const duplicateRatio = Number(summary.duplicate_photo_review_ratio || 0);
  if (duplicatePhotoReviews <= 0 || largestCluster <= 1) {
    return null;
  }

  return locale === "ru"
    ? `Photo-forensics слой нашел reuse покупательских фото: ${duplicatePhotoReviews} отзыв(ов), крупнейший shared-photo кластер - ${largestCluster}, доля среди отзывов с фото около ${Math.round(duplicateRatio * 100)}%.`
    : `The photo-forensics layer found customer-photo reuse across ${duplicatePhotoReviews} review(s); the largest shared-photo cluster spans ${largestCluster}, about ${Math.round(duplicateRatio * 100)}% of reviews with photos.`;
}

function buildPhotoTemporalClusterInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const clusteredReviews = Number(summary.photo_temporal_cluster_reviews || 0);
  const clusteredRatio = Number(summary.photo_temporal_cluster_ratio || 0);
  const windowHours = Number(summary.photo_temporal_cluster_window_hours || 48);
  if (clusteredReviews <= 0) {
    return null;
  }

  return locale === "ru"
    ? `Temporal photo-layer нашел coordinated reuse: ${clusteredReviews} отзыв(ов) используют одно и то же фото у разных авторов в пределах ${Math.round(windowHours)} часов; доля среди фото-отзывов около ${Math.round(clusteredRatio * 100)}%.`
    : `The temporal photo layer found coordinated reuse: ${clusteredReviews} review(s) share the same image across different authors inside a ${Math.round(windowHours)}-hour window, about ${Math.round(clusteredRatio * 100)}% of photo reviews.`;
}

function buildImageAlignmentInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const mismatchReviews = Number(summary.image_alignment_mismatch_reviews || 0);
  const evaluatedReviews = Number(summary.image_alignment_reviews || 0);
  const modelStatus = String(summary.image_alignment_model_status || "");
  if (mismatchReviews > 0) {
    return locale === "ru"
      ? `CLIP/ViT слой нашел ${mismatchReviews} фото, которые визуально слабее совпадают с текстом отзыва или категорией товара. Проверено фото-отзывов: ${evaluatedReviews}.`
      : `The CLIP/ViT layer found ${mismatchReviews} photo(s) that weakly match the review text or inferred product category. Evaluated photo reviews: ${evaluatedReviews}.`;
  }
  if (modelStatus === "not_configured" || modelStatus === "model_unavailable") {
    return locale === "ru"
      ? "Фото извлечены, но CLIP/ViT alignment еще не настроен на этой машине: установите transformers/Pillow и модель включится без изменений фронтенда."
      : "Photos were extracted, but CLIP/ViT alignment is not configured on this machine yet; install transformers/Pillow and the model will activate without frontend changes.";
  }
  return null;
}

function buildStockMarketingInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const stockReviews = Number(summary.stock_marketing_photo_reviews || 0);
  const stockRatio = Number(summary.stock_marketing_photo_ratio || 0);
  if (stockReviews <= 0) {
    return null;
  }

  return locale === "ru"
    ? `Stock/marketing слой пометил ${stockReviews} фото как похожие на каталог, студийный рендер, баннер или listing-скрин. Доля среди отзывов с фото около ${Math.round(stockRatio * 100)}%.`
    : `The stock/marketing layer flagged ${stockReviews} photo(s) that look like catalog, studio render, banner, or listing assets. About ${Math.round(stockRatio * 100)}% of photo reviews.`;
}

function buildSyntheticImageInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const syntheticReviews = Number(summary.synthetic_image_reviews || 0);
  const syntheticRatio = Number(summary.synthetic_image_ratio || 0);
  if (syntheticReviews <= 0) {
    return null;
  }

  return locale === "ru"
    ? `AI/synthetic image слой дал слабую подсказку по ${syntheticReviews} фото (${Math.round(syntheticRatio * 100)}% фото-отзывов). Это supporting evidence, а не самостоятельное доказательство.`
    : `The AI/synthetic image layer produced weak hints on ${syntheticReviews} photo(s), about ${Math.round(syntheticRatio * 100)}% of photo reviews. This is supporting evidence, not standalone proof.`;
}

function buildImageOcrInsight(summary: Record<string, unknown> | undefined, locale: Locale): string | null {
  if (!summary) {
    return null;
  }

  const flaggedReviews = Number(summary.image_ocr_flagged_reviews || 0);
  const flaggedRatio = Number(summary.image_ocr_flagged_ratio || 0);
  const status = String(summary.image_ocr_status || "");
  if (flaggedReviews > 0) {
    return locale === "ru"
      ? `OCR по фото нашел промо-надписи, watermark, контакты или marketplace branding в ${flaggedReviews} фото (${Math.round(flaggedRatio * 100)}% OCR-проверенных фото).`
      : `Photo OCR found promo text, watermarks, contact handles, or marketplace branding in ${flaggedReviews} photo(s), ${Math.round(flaggedRatio * 100)}% of OCR-checked photos.`;
  }
  if (status === "not_configured" || status === "engine_unavailable") {
    return locale === "ru"
      ? "Фото извлечены, но OCR пока не настроен: установите pytesseract и системный Tesseract, чтобы читать watermark/promo-текст на изображениях."
      : "Photos were extracted, but OCR is not configured yet; install pytesseract and the system Tesseract engine to read watermark/promo text.";
  }
  return null;
}

function buildUncertaintyDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const manualReviewRatio = Number(summary.manual_review_ratio || 0);
  const uncertaintyMean = Number(summary.uncertainty_mean || 0);
  const oodAlertRatio = Number(summary.ood_alert_ratio || 0);
  if (manualReviewRatio <= 0 && uncertaintyMean <= 0 && oodAlertRatio <= 0) {
    return null;
  }

  const score = Math.round(
    clamp((manualReviewRatio * 0.52 + uncertaintyMean * 0.28 + oodAlertRatio * 0.20) * 100, 8, 98)
  );

  return {
    id: "uncertainty-gate",
    name: locale === "ru" ? "Шлюз неопределенности" : "Uncertainty Gate",
    description:
      locale === "ru"
        ? "Отправляет неоднозначные, конфликтующие или out-of-domain отзывы на ручную модерацию вместо жесткого ярлыка."
        : "Routes ambiguous, conflicting, or out-of-domain reviews into manual moderation instead of forcing a hard label.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildSyntheticImageDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const syntheticReviews = Number(summary.synthetic_image_reviews || 0);
  const syntheticRatio = Number(summary.synthetic_image_ratio || 0);
  const scoreMean = Number(summary.synthetic_image_score_mean || 0);
  if (syntheticReviews <= 0) {
    return null;
  }

  const score = Math.round(clamp((syntheticRatio * 0.46 + scoreMean * 0.54) * 100, 10, 82));

  return {
    id: "ai-synthetic-image",
    name: locale === "ru" ? "AI/synthetic image hint" : "AI/Synthetic Image Hint",
    description:
      locale === "ru"
        ? "Слабый вспомогательный сигнал: ищет AI-generated, diffusion/CGI и synthetic cues, но не использует их как главное доказательство."
        : "Weak auxiliary signal for AI-generated, diffusion/CGI, and synthetic cues; never treated as primary evidence.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildImageOcrDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const flaggedReviews = Number(summary.image_ocr_flagged_reviews || 0);
  const flaggedRatio = Number(summary.image_ocr_flagged_ratio || 0);
  const scoreMean = Number(summary.image_ocr_score_mean || 0);
  if (flaggedReviews <= 0) {
    return null;
  }

  const score = Math.round(clamp((flaggedRatio * 0.58 + scoreMean * 0.42) * 100, 18, 96));

  return {
    id: "image-ocr-text",
    name: locale === "ru" ? "OCR текста на фото" : "Photo OCR Text",
    description:
      locale === "ru"
        ? "Извлекает текст с фото и ловит promo/sale-надписи, watermark, contacts, marketplace branding и чужие магазинные следы."
        : "Extracts image text and flags promo/sale copy, watermarks, contacts, marketplace branding, and foreign store traces.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildStockMarketingDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const stockReviews = Number(summary.stock_marketing_photo_reviews || 0);
  const stockRatio = Number(summary.stock_marketing_photo_ratio || 0);
  const scoreMean = Number(summary.stock_marketing_score_mean || 0);
  if (stockReviews <= 0) {
    return null;
  }

  const score = Math.round(clamp((stockRatio * 0.62 + scoreMean * 0.38) * 100, 14, 98));

  return {
    id: "stock-marketing-photo",
    name: locale === "ru" ? "Стоковые/маркетинговые фото" : "Stock/Marketing Photos",
    description:
      locale === "ru"
        ? "Отделяет реальные customer snapshots от каталожных фото, студийных рендеров, баннеров и listing-скриншотов."
        : "Separates real customer snapshots from catalog photos, studio renders, banners, and listing screenshots.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildImageAlignmentDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const mismatchReviews = Number(summary.image_alignment_mismatch_reviews || 0);
  const mismatchRatio = Number(summary.image_alignment_mismatch_ratio || 0);
  const evaluatedReviews = Number(summary.image_alignment_reviews || 0);
  const modelStatus = String(summary.image_alignment_model_status || "");
  if (mismatchReviews <= 0 && modelStatus !== "ready") {
    return null;
  }
  if (evaluatedReviews <= 0 && mismatchReviews <= 0) {
    return null;
  }

  const score = Math.round(clamp((mismatchRatio * 0.74 + Math.min(mismatchReviews / 5, 1) * 0.26) * 100, 12, 98));

  return {
    id: "image-text-alignment",
    name: locale === "ru" ? "Фото vs текст отзыва" : "Photo vs Review Text",
    description:
      locale === "ru"
        ? "Сравнивает покупательское фото с текстом отзыва и предполагаемой категорией товара через CLIP/ViT similarity."
        : "Compares customer photos against the review text and inferred product category using CLIP/ViT similarity.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildPhotoTemporalClusterDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const clusteredReviews = Number(summary.photo_temporal_cluster_reviews || 0);
  const clusteredRatio = Number(summary.photo_temporal_cluster_ratio || 0);
  const largestCluster = Number(summary.largest_photo_temporal_cluster || 0);
  if (clusteredReviews <= 0 || largestCluster <= 1) {
    return null;
  }

  const score = Math.round(
    clamp((clusteredRatio * 0.58 + Math.min(largestCluster / 5, 1) * 0.42) * 100, 20, 98)
  );

  return {
    id: "timed-photo-cluster",
    name: locale === "ru" ? "Временной кластер фото" : "Timed Photo Cluster",
    description:
      locale === "ru"
        ? "Ловит coordinated campaign: одно и то же customer photo появляется у разных авторов в коротком временном окне."
        : "Flags coordinated campaigns where the same customer photo appears across different authors inside a short time window.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function buildPhotoForensicsDetectorCard(summary: Record<string, unknown> | undefined, locale: Locale): DetectorCardData | null {
  if (!summary) {
    return null;
  }

  const duplicatePhotoReviews = Number(summary.duplicate_photo_reviews || 0);
  const duplicateRatio = Number(summary.duplicate_photo_review_ratio || 0);
  const largestCluster = Number(summary.largest_duplicate_photo_cluster || 0);
  if (duplicatePhotoReviews <= 0 || largestCluster <= 1) {
    return null;
  }

  const score = Math.round(
    clamp((duplicateRatio * 0.68 + Math.min(largestCluster / 5, 1) * 0.32) * 100, 18, 98)
  );

  return {
    id: "customer-photo-reuse",
    name: locale === "ru" ? "Дубликаты фото покупателей" : "Customer Photo Reuse",
    description:
      locale === "ru"
        ? "Ловит повторное использование одних и тех же покупательских фото между отзывами, включая CDN-варианты с разными resize/query параметрами."
        : "Detects reuse of the same customer-submitted images across reviews, including CDN variants with different resize/query parameters.",
    score,
    severity: severityFromScore(score),
    status: detectorStatusFromScore(score),
  };
}

function synthesizeDetectorCards(
  anomalyTypes: AnomalyTypePoint[],
  riskScore: number,
  summary: Record<string, unknown> | undefined,
  locale: Locale
): DetectorCardData[] {
  const reasonLookup = new Map(anomalyTypes.map((item) => [item.type.toLowerCase(), item.count]));
  const scoreFromCount = (keywords: string[], base: number) => {
    const matched = Array.from(reasonLookup.entries())
      .filter(([key]) => keywords.some((keyword) => key.includes(keyword)))
      .reduce((sum, [, count]) => sum + count, 0);
    return clamp(base + matched * 6, 18, 96);
  };

  const specs =
    locale === "ru"
      ? [
          {
            id: "text-similarity",
            name: "Пик текстовой схожести",
            description: "Фиксирует почти дублирующиеся тексты и повторяющиеся лексические структуры.",
            score: scoreFromCount(["repetition", "duplicate", "similarity", "схож"], riskScore * 0.55),
          },
          {
            id: "burst-posting",
            name: "Паттерн всплеска публикаций",
            description: "Подсвечивает короткие интервалы с необычно плотной активностью.",
            score: scoreFromCount(["burst", "cluster", "same day", "всплеск"], riskScore * 0.52),
          },
          {
            id: "reviewer-trust",
            name: "Аномалия доверия к авторам",
            description: "Фокусируется на повторяющихся авторах и несогласованности trust-сигналов.",
            score: scoreFromCount(["author", "reviewer", "автор"], riskScore * 0.46),
          },
          {
            id: "rating-shift",
            name: "Сдвиг распределения рейтингов",
            description: "Ловит подозрительный дрейф к экстремальным или стратегически синхронизированным оценкам.",
            score: scoreFromCount(["rating", "extreme", "рейтинг"], riskScore * 0.5),
          },
          {
            id: "sentiment-repetition",
            name: "Повтор sentiment-паттернов",
            description: "Определяет переиспользование одинаковой полярности и шаблонного эмоционального фрейминга.",
            score: scoreFromCount(["sentiment", "promotional", "templated", "эмоцион"], riskScore * 0.44),
          },
          {
            id: "temporal-clustering",
            name: "Временная кластеризация",
            description: "Измеряет, приходят ли отзывы волнами вместо органичного распределения по времени.",
            score: scoreFromCount(["temporal", "cluster", "same day", "времен"], riskScore * 0.48),
          },
        ]
      : [
          {
            id: "text-similarity",
            name: "Text Similarity Spike",
            description: "Flags near-duplicate review bodies and repeated lexical structures.",
            score: scoreFromCount(["repetition", "duplicate", "similarity"], riskScore * 0.55),
          },
          {
            id: "burst-posting",
            name: "Burst Posting Pattern",
            description: "Highlights short intervals with unusually dense publishing activity.",
            score: scoreFromCount(["burst", "cluster", "same day"], riskScore * 0.52),
          },
          {
            id: "reviewer-trust",
            name: "Reviewer Trust Anomaly",
            description: "Focuses on repeated author presence and trust inconsistencies.",
            score: scoreFromCount(["author", "reviewer"], riskScore * 0.46),
          },
          {
            id: "rating-shift",
            name: "Rating Distribution Shift",
            description: "Captures suspicious drift toward extreme or strategically timed scores.",
            score: scoreFromCount(["rating", "extreme"], riskScore * 0.5),
          },
          {
            id: "sentiment-repetition",
            name: "Sentiment Repetition",
            description: "Detects over-reused polarity patterns and templated emotional framing.",
            score: scoreFromCount(["sentiment", "promotional", "templated"], riskScore * 0.44),
          },
          {
            id: "temporal-clustering",
            name: "Temporal Clustering",
            description: "Measures whether reviews arrive in clustered waves instead of organic spread.",
            score: scoreFromCount(["temporal", "cluster", "same day"], riskScore * 0.48),
          },
        ];

  const slangCard = buildSlangDetectorCard(summary, locale);
  const uncertaintyCard = buildUncertaintyDetectorCard(summary, locale);
  const imageAlignmentCard = buildImageAlignmentDetectorCard(summary, locale);
  const stockMarketingCard = buildStockMarketingDetectorCard(summary, locale);
  const syntheticImageCard = buildSyntheticImageDetectorCard(summary, locale);
  const imageOcrCard = buildImageOcrDetectorCard(summary, locale);
  const photoTemporalClusterCard = buildPhotoTemporalClusterDetectorCard(summary, locale);
  const photoForensicsCard = buildPhotoForensicsDetectorCard(summary, locale);
  const cards = [
    ...specs,
    ...(slangCard ? [slangCard] : []),
    ...(uncertaintyCard ? [uncertaintyCard] : []),
    ...(imageAlignmentCard ? [imageAlignmentCard] : []),
    ...(stockMarketingCard ? [stockMarketingCard] : []),
    ...(syntheticImageCard ? [syntheticImageCard] : []),
    ...(imageOcrCard ? [imageOcrCard] : []),
    ...(photoTemporalClusterCard ? [photoTemporalClusterCard] : []),
    ...(photoForensicsCard ? [photoForensicsCard] : []),
  ];

  return cards.map((item) => ({
    ...item,
    severity: severityFromScore(item.score),
    status: detectorStatusFromScore(item.score),
    score: Math.round(item.score),
  }));
}

function buildActivitySeries(reviews: Array<Record<string, unknown>>, locale: Locale) {
  const dated = reviews
    .map((review) => ({
      date: String(review.date || "Undated"),
      suspicious: Number(review.suspicious_probability || 0) >= 0.55 ? 1 : 0,
    }))
    .filter((item) => item.date && item.date !== "Undated");

  if (!dated.length) {
    return locale === "ru"
      ? [
          { label: "T-6", reviews: 9, suspicious: 1 },
          { label: "T-5", reviews: 12, suspicious: 2 },
          { label: "T-4", reviews: 17, suspicious: 2 },
          { label: "T-3", reviews: 22, suspicious: 4 },
          { label: "T-2", reviews: 19, suspicious: 5 },
          { label: "T-1", reviews: 24, suspicious: 7 },
          { label: "Сейчас", reviews: 18, suspicious: 4 },
        ]
      : [
          { label: "T-6", reviews: 9, suspicious: 1 },
          { label: "T-5", reviews: 12, suspicious: 2 },
          { label: "T-4", reviews: 17, suspicious: 2 },
          { label: "T-3", reviews: 22, suspicious: 4 },
          { label: "T-2", reviews: 19, suspicious: 5 },
          { label: "T-1", reviews: 24, suspicious: 7 },
          { label: "Now", reviews: 18, suspicious: 4 },
        ];
  }

  const grouped = new Map<string, { reviews: number; suspicious: number }>();
  dated.forEach((item) => {
    const key = item.date.slice(0, 10);
    const current = grouped.get(key) || { reviews: 0, suspicious: 0 };
    current.reviews += 1;
    current.suspicious += item.suspicious;
    grouped.set(key, current);
  });

  return Array.from(grouped.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .slice(-7)
    .map(([label, value]) => ({
      label,
      reviews: value.reviews,
      suspicious: value.suspicious,
    }));
}

function buildSuspiciousReviews(reviews: Array<Record<string, unknown>>, locale: Locale): SuspiciousReviewRow[] {
  const rows = reviews
    .map((review, index) => {
      const probability = Number(review.suspicious_probability || 0);
      const triageStatus = String(
        review.triage_label ||
          (Number(review.requires_manual_review || 0) === 1
            ? "needs_manual_review"
            : Number(review.is_suspicious || 0) === 1
              ? "confident_suspicious"
              : "confident_clean")
      ) as ReviewTriageStatus;
      const reasons = Array.isArray(review.suspicion_reasons) ? review.suspicion_reasons.map(String) : [];
      const manualReviewReasons = Array.isArray(review.manual_review_reasons)
        ? review.manual_review_reasons.map(String)
        : [];
      const uncertaintyScore = Number(review.uncertainty_score || 0);
      const imageUrls = Array.isArray(review.image_urls) ? review.image_urls.map(String) : [];
      const fallbackReason =
        triageStatus === "needs_manual_review"
          ? locale === "ru"
            ? "Модель направила этот отзыв на ручную модерацию."
            : "The model routed this review to manual moderation."
          : locale === "ru"
            ? "Гибридный детектор посчитал этот отзыв нетипичным."
            : "Hybrid detector considered this review unusual.";

      return {
        id: String(review.review_id || index + 1),
        title: String(review.title || (locale === "ru" ? "Отзыв без заголовка" : "Untitled review")),
        text: String(review.review_text || ""),
        rating: Number(review.rating || 0),
        suspiciousness: probability,
        reason: localizeKnownText(
          String((triageStatus === "needs_manual_review" ? manualReviewReasons[0] : reasons[0]) || fallbackReason),
          locale
        ),
        author: String(review.author || (locale === "ru" ? "Неизвестный автор" : "Unknown author")),
        authorTrust: authorTrustFromTriage(triageStatus, probability),
        date: String(review.date || (locale === "ru" ? "Без даты" : "Undated")),
        severity: triageSeverity(triageStatus, probability, uncertaintyScore),
        triageStatus,
        languageProfile: String(review.slang_profile_label || "neutral") as SuspiciousReviewRow["languageProfile"],
        detectedTerms: Array.isArray(review.detected_slang_terms) ? review.detected_slang_terms.map(String).slice(0, 5) : [],
        languageSignalScore: Number(review.slang_manipulation_score || 0),
        languageAuthenticityScore: Number(review.slang_authenticity_score || 0.5),
        languageDomain: humanizeDomainLabel(String(review.slang_domain_label || "general"), locale),
        templateClustered: Number(review.slang_template_dup_count || 0) >= 2,
        uncertaintyScore,
        oodScore: Number(review.ood_score || 0),
        imageUrls,
        imageCount: Number(review.image_count || imageUrls.length),
        duplicateImageCount: Number(review.duplicate_image_count || 0),
        duplicateImageClusterSize: Number(review.duplicate_image_cluster_size || 0),
        duplicateImageScore: Number(review.duplicate_image_score || 0),
        duplicateImageFlag: Number(review.duplicate_image_flag || 0) === 1,
        imageTemporalClusterScore: Number(review.image_temporal_cluster_score || 0),
        imageTemporalClusterFlag: Number(review.image_temporal_cluster_flag || 0) === 1,
        imageTemporalClusterSize: Number(review.image_temporal_cluster_size || 0),
        imageTemporalClusterAuthorCount: Number(review.image_temporal_cluster_author_count || 0),
        imageTemporalClusterWindowHours: Number(review.image_temporal_cluster_window_hours || 0),
        imageTextAlignmentScore: Number(review.image_text_alignment_score || 0),
        imageTextMismatchScore: Number(review.image_text_mismatch_score || 0),
        imageTextMismatchFlag: Number(review.image_text_mismatch_flag || 0) === 1,
        imageTextAlignmentLabel: String(review.image_text_alignment_label || "not_evaluated"),
        imageStockMarketingScore: Number(review.image_stock_marketing_score || 0),
        imageStockMarketingFlag: Number(review.image_stock_marketing_flag || 0) === 1,
        imageStockMarketingLabel: String(review.image_stock_marketing_label || "not_evaluated"),
        imageSyntheticScore: Number(review.image_synthetic_score || 0),
        imageSyntheticFlag: Number(review.image_synthetic_flag || 0) === 1,
        imageSyntheticLabel: String(review.image_synthetic_label || "not_evaluated"),
        imageOcrScore: Number(review.image_ocr_score || 0),
        imageOcrFlag: Number(review.image_ocr_flag || 0) === 1,
        imageOcrText: String(review.image_ocr_text || ""),
        imageOcrLabels: Array.isArray(review.image_ocr_labels) ? review.image_ocr_labels.map(String) : [],
      } satisfies SuspiciousReviewRow;
    })
    .sort((left, right) => right.suspiciousness - left.suspiciousness);

  return rows.slice(0, 12);
}

function buildAnomalyTypesFromReviews(response: ReviewApiResponse, locale: Locale): AnomalyTypePoint[] {
  const topReasons = Array.isArray(response.highlights?.top_reasons)
    ? response.highlights?.top_reasons
    : [];

  if (topReasons.length) {
    return topReasons.map((item) => ({
      type: localizeKnownText(String(item.reason || (locale === "ru" ? "Неизвестный сигнал" : "Unknown signal")), locale),
      count: Number(item.count || 0),
    }));
  }

  const allReasons = Array.isArray(response.reviews)
    ? response.reviews.flatMap((review) =>
        Array.isArray(review.suspicion_reasons) ? review.suspicion_reasons.map(String) : []
      )
    : [];

  return groupCounts(allReasons)
    .sort((left, right) => right.count - left.count)
    .slice(0, 6)
    .map((entry) => ({
      type: localizeKnownText(entry.label, locale),
      count: entry.count,
    }));
}

function buildSummaryFallbackAnomalyTypes(
  summary: Record<string, unknown>,
  visibleReviewCount: number,
  locale: Locale
): AnomalyTypePoint[] {
  const totalReviews = Number(summary.total_reviews || visibleReviewCount || 0);
  const suspiciousRatio = Number(summary.suspicious_ratio || 0);
  const manipulationMean = Number(summary.manipulation_score_mean || 0);
  const highestProbability = Number(summary.highest_probability || 0);
  const manualReviewRatio = Number(
    summary.manual_review_ratio ||
      Number(summary.manual_review_reviews || 0) / Math.max(totalReviews, 1)
  );
  const duplicatePhotoRatio = Number(summary.duplicate_photo_review_ratio || 0);
  const temporalPhotoRatio = Number(summary.photo_temporal_cluster_ratio || 0);
  const imageMismatchRatio = Number(summary.image_alignment_mismatch_ratio || 0);
  const photoSignal = Math.max(duplicatePhotoRatio, temporalPhotoRatio, imageMismatchRatio);

  const candidates = [
    { type: "Suspicious review ratio", value: suspiciousRatio },
    { type: "Behavioral manipulation score", value: manipulationMean },
    { type: "Peak suspicious probability", value: highestProbability },
    { type: "Manual review uncertainty", value: manualReviewRatio },
    { type: "Photo forensics signal", value: photoSignal },
  ]
    .filter((item) => Number.isFinite(item.value) && item.value > 0)
    .sort((left, right) => right.value - left.value)
    .slice(0, 5)
    .map((item) => ({
      type: localizeKnownText(item.type, locale),
      count: Math.max(1, Math.round(clamp(item.value, 0.01, 1) * 100)),
    }));

  if (candidates.length) {
    return candidates;
  }

  return [
    {
      type: localizeKnownText(totalReviews > 0 ? "Low-risk review profile" : "Extraction coverage", locale),
      count: Math.max(1, totalReviews || 1),
    },
  ];
}

function verdictFromRisk(score: number, suspiciousCount: number, manualReviewCount: number, locale: Locale) {
  if (score >= 80) {
    return locale === "ru"
      ? `Страница показывает сильные признаки манипуляции: ${suspiciousCount} отзывов уверенно помечены как подозрительные, а ${manualReviewCount} направлены на ручную проверку.`
      : `The page presents strong evidence of manipulated review behavior with ${suspiciousCount} confidently suspicious reviews and ${manualReviewCount} items routed to manual review.`;
  }
  if (score >= 60) {
    return locale === "ru"
      ? `В выборке видны смешанные паттерны подлинности, а еще ${manualReviewCount} отзыв(ов) требуют решения человека, прежде чем рейтинговому профилю можно доверять.`
      : `The review set shows mixed authenticity patterns and ${manualReviewCount} review(s) still need a human decision before the rating profile can be trusted.`;
  }
  return locale === "ru"
    ? "Видимая выборка отзывов выглядит сравнительно стабильной, хотя базовые модерационные проверки все равно рекомендуются."
    : "The visible review sample looks comparatively stable, although normal moderation checks are still recommended.";
}

function statusFromRisk(score: number, locale: Locale) {
  if (score >= 80) {
    return locale === "ru" ? "Высокий fraud-риск" : "High fraud risk";
  }
  if (score >= 60) {
    return locale === "ru" ? "Под наблюдением" : "Watchlist";
  }
  return locale === "ru" ? "Низкорисковая выборка" : "Low-risk sample";
}

function transformReviewModeResponse(response: ReviewApiResponse, sourceMode: SourceMode, locale: Locale): DashboardResult {
  const summary = response.summary || {};
  const reviews = Array.isArray(response.reviews) ? response.reviews : [];
  const suspiciousRatio = Number(summary.suspicious_ratio || 0);
  const manipulationMean = Number(summary.manipulation_score_mean || 0);
  const highestProbability = Number(summary.highest_probability || 0);
  const manualReviewCount = Number(
    summary.manual_review_reviews ||
      reviews.filter((review) => String(review.triage_label || "") === "needs_manual_review").length
  );
  const suspiciousCount = Number(
    summary.confident_suspicious_reviews ||
      reviews.filter((review) => String(review.triage_label || "") === "confident_suspicious").length ||
      summary.suspicious_reviews ||
      reviews.filter((review) => Number(review.is_suspicious || 0) === 1).length
  );
  const confidentCleanCount = Number(
    summary.confident_clean_reviews ||
      reviews.filter((review) => String(review.triage_label || "") === "confident_clean").length ||
      Math.max(Number(summary.total_reviews || reviews.length) - suspiciousCount - manualReviewCount, 0)
  );
  const reviewCount = Number(summary.total_reviews || reviews.length);
  const hasTriageSummary =
    summary.automated_decision_ratio !== undefined ||
    summary.manual_review_reviews !== undefined ||
    summary.confident_suspicious_reviews !== undefined ||
    summary.confident_clean_reviews !== undefined;
  const automatedDecisionRatio = Number(
    hasTriageSummary
      ? summary.automated_decision_ratio ||
          Math.max(reviewCount - manualReviewCount, 0) / Math.max(reviewCount, 1)
      : 1
  );
  const uncertaintyMean = Number(summary.uncertainty_mean || 0);
  const riskScore = Math.round(
    clamp(
      (
        suspiciousRatio * 0.50 +
        manipulationMean * 0.28 +
        highestProbability * 0.12 +
        Math.min(manualReviewCount / Math.max(reviewCount, 1), 0.35) * 0.10
      ) * 100,
      12,
      98
    )
  );
  const confidence = Math.round(
    clamp((automatedDecisionRatio * 0.72 + Math.max(0, 1 - uncertaintyMean) * 0.28) * 100, 52, 97)
  );
  const anomalyTypes = buildAnomalyTypesFromReviews(response, locale);
  const detectorCards = synthesizeDetectorCards(anomalyTypes, riskScore, summary, locale);
  const slangInsight = buildSlangInsight(summary, locale);
  const photoInsight = buildPhotoForensicsInsight(summary, locale);
  const photoTemporalClusterInsight = buildPhotoTemporalClusterInsight(summary, locale);
  const imageAlignmentInsight = buildImageAlignmentInsight(summary, locale);
  const stockMarketingInsight = buildStockMarketingInsight(summary, locale);
  const syntheticImageInsight = buildSyntheticImageInsight(summary, locale);
  const imageOcrInsight = buildImageOcrInsight(summary, locale);
  const explainabilitySeed =
    anomalyTypes.length > 0 ? anomalyTypes : buildSummaryFallbackAnomalyTypes(summary, reviews.length, locale);
  const keyInsights = Array.isArray(response.highlights?.notes)
    ? response.highlights?.notes.map((note) => localizeKnownText(String(note), locale))
    : [
        locale === "ru"
          ? "Гибридный скор объединяет текстовую подозрительность с поведенческими сигналами манипуляции."
          : "Hybrid score combines text suspiciousness with behavioral manipulation signals.",
      ];

  if (slangInsight) {
    keyInsights.unshift(slangInsight);
  }
  if (photoInsight) {
    keyInsights.unshift(photoInsight);
  }
  if (photoTemporalClusterInsight) {
    keyInsights.unshift(photoTemporalClusterInsight);
  }
  if (imageAlignmentInsight) {
    keyInsights.unshift(imageAlignmentInsight);
  }
  if (stockMarketingInsight) {
    keyInsights.unshift(stockMarketingInsight);
  }
  if (imageOcrInsight) {
    keyInsights.unshift(imageOcrInsight);
  }
  if (syntheticImageInsight) {
    keyInsights.push(syntheticImageInsight);
  }
  if (manualReviewCount > 0) {
    keyInsights.unshift(
      locale === "ru"
        ? `${manualReviewCount} отзыв(ов) были отправлены на ручную проверку, потому что модель увидела неопределенность или out-of-domain-паттерны.`
        : `${manualReviewCount} review(s) were routed to manual review because the model detected uncertainty or out-of-domain patterns.`
    );
  }

  return {
    sourceMode,
    overview: {
      productName: String(summary.source_site || response.request?.source_site || (locale === "ru" ? "Страница отзывов товара" : "Product review page")),
      sourceLabel: String(summary.source_site || response.request?.source_site || "unknown"),
      statusLabel: statusFromRisk(riskScore, locale),
      riskScore,
      manipulationProbability: Math.round(clamp((manipulationMean * 0.6 + suspiciousRatio * 0.4) * 100, 8, 96)),
      confidence,
      reviewCount,
      suspiciousCount,
      manualReviewCount,
      verdict: verdictFromRisk(riskScore, suspiciousCount, manualReviewCount, locale),
    },
    trustBreakdown: [
      { name: locale === "ru" ? "Надежные" : "Trustworthy", value: Math.max(confidentCleanCount, 0), fill: "#0f766e" },
      { name: locale === "ru" ? "Подозрительные" : "Suspicious", value: Math.max(suspiciousCount, 0), fill: "#c35e43" },
      { name: locale === "ru" ? "Неопределенные" : "Uncertain", value: Math.max(manualReviewCount, 0), fill: "#c4872f" },
    ],
    activitySeries: buildActivitySeries(reviews, locale),
    anomalyTypes: anomalyTypes.length > 0 ? anomalyTypes : explainabilitySeed,
    detectorCards,
    explainability: buildExplainability(explainabilitySeed, locale),
    suspiciousReviews: buildSuspiciousReviews(reviews, locale),
    keyInsights: keyInsights.slice(0, 3),
  };
}

function transformRecordsModeResponse(response: ReviewApiResponse, locale: Locale): DashboardResult {
  const predictions = Array.isArray(response.predictions) ? response.predictions : [];
  const suspiciousUsers = Array.isArray(response.suspicious_users) ? response.suspicious_users : [];
  const totalRecords = Number(response.summary?.total_records || predictions.length);
  const slangFlaggedRatings = Number(response.summary?.slang_flagged_ratings || 0);
  const suspiciousCount = Number(
    response.summary?.suspicious_ratings ||
      predictions.filter((row) => Number(row.is_suspicious || 0) === 1).length
  );
  const riskScore = Math.round(clamp((suspiciousCount / Math.max(totalRecords, 1)) * 100 * 1.25, 10, 98));
  const anomalyReasons = predictions.flatMap((row) =>
    Array.isArray(row.suspicion_reasons) ? row.suspicion_reasons.map(String) : []
  );
  const anomalyTypes = groupCounts(anomalyReasons)
    .sort((left, right) => right.count - left.count)
    .slice(0, 6)
    .map((entry) => ({ type: localizeKnownText(entry.label, locale), count: entry.count || 1 }));

  const suspiciousReviews: SuspiciousReviewRow[] = predictions
    .filter((row) => Number(row.is_suspicious || 0) === 1)
    .sort((left, right) => Number(right.anomaly_score || 0) - Number(left.anomaly_score || 0))
    .slice(0, 12)
    .map((row, index) => ({
      id: String(index + 1),
      title: `${String(row.user_id || "unknown")} -> ${String(row.item_id || "item")}`,
      text: String(row.review_text || ""),
      rating: Number(row.rating || 0),
      suspiciousness: Number(row.anomaly_score || 0),
      reason: localizeKnownText(
        String(
          (Array.isArray(row.suspicion_reasons) && row.suspicion_reasons[0]) ||
            (locale === "ru"
              ? "Поведенческий автоэнкодер отметил эту запись как аномальную."
              : "Behavioral autoencoder marked this record as anomalous.")
        ),
        locale
      ),
      author: String(row.user_id || "unknown"),
      authorTrust: "low",
      date: String(row.timestamp || (locale === "ru" ? "Без даты" : "Undated")),
      severity: severityFromScore(Number(row.anomaly_score || 0) * 100),
      triageStatus: "confident_suspicious",
      languageProfile: String(row.slang_profile_label || "neutral") as SuspiciousReviewRow["languageProfile"],
      detectedTerms: Array.isArray(row.slang_terms)
        ? row.slang_terms.map(String).slice(0, 5)
        : Array.isArray(row.detected_slang_terms)
          ? row.detected_slang_terms.map(String).slice(0, 5)
          : [],
      languageSignalScore: Number(row.slang_manipulation_score || 0),
      languageAuthenticityScore: Number(row.slang_authenticity_score || 0.5),
      languageDomain: humanizeDomainLabel(String(row.slang_domain_label || response.summary?.slang_domain_label || "general"), locale),
      templateClustered: Number(row.slang_template_dup_count || 0) >= 2,
      uncertaintyScore: 0,
      oodScore: 0,
      imageUrls: [],
      imageCount: 0,
      duplicateImageCount: 0,
      duplicateImageClusterSize: 0,
      duplicateImageScore: 0,
      duplicateImageFlag: false,
      imageTextAlignmentScore: 0,
      imageTextMismatchScore: 0,
      imageTextMismatchFlag: false,
      imageTextAlignmentLabel: "not_evaluated",
      imageStockMarketingScore: 0,
      imageStockMarketingFlag: false,
      imageStockMarketingLabel: "not_evaluated",
      imageSyntheticScore: 0,
      imageSyntheticFlag: false,
      imageSyntheticLabel: "not_evaluated",
      imageOcrScore: 0,
      imageOcrFlag: false,
      imageOcrText: "",
      imageOcrLabels: [],
    }));

  const syntheticActivity = predictions.slice(0, 7).map((row, index) => ({
    label:
      String(row.timestamp || `${locale === "ru" ? "Окно" : "Window"} ${index + 1}`).slice(0, 10) ||
      `${locale === "ru" ? "Окно" : "Window"} ${index + 1}`,
    reviews: Math.max(3, Math.round(totalRecords / 7)),
    suspicious: Number(row.is_suspicious || 0) ? 1 + (index % 3) : index % 2,
  }));

  const detectorSeed =
    anomalyTypes.length > 0
      ? anomalyTypes
      : [
          { type: localizeKnownText("User cluster anomaly", locale), count: suspiciousUsers.length || 1 },
          { type: localizeKnownText("Threshold breach", locale), count: suspiciousCount || 1 },
        ];

  return {
    sourceMode: "records",
    overview: {
      productName: locale === "ru" ? "Структурированный набор рейтингов сайта" : "Structured site rating dataset",
      sourceLabel: "site-data",
      statusLabel: statusFromRisk(riskScore, locale),
      riskScore,
      manipulationProbability: riskScore,
      confidence: Math.round(clamp(72 + suspiciousUsers.length * 4, 65, 98)),
      reviewCount: totalRecords,
      suspiciousCount,
      manualReviewCount: 0,
      verdict:
        suspiciousCount > 0
          ? locale === "ru"
            ? `Структурированные site-data показывают ${suspiciousCount} подозрительных рейтингов и ${suspiciousUsers.length} подозрительных user-кластеров.`
            : `Structured site records expose ${suspiciousCount} suspicious ratings and ${suspiciousUsers.length} suspicious user clusters.`
          : locale === "ru"
            ? "Текущий структурированный датасет не показывает сильных сигналов накрутки рейтингов."
            : "The current structured dataset does not expose strong rating manipulation signals.",
    },
    trustBreakdown: [
      { name: locale === "ru" ? "Надежные" : "Trustworthy", value: Math.max(totalRecords - suspiciousCount, 0), fill: "#0f766e" },
      { name: locale === "ru" ? "Подозрительные" : "Suspicious", value: suspiciousCount, fill: "#c35e43" },
      { name: locale === "ru" ? "Неопределенные" : "Uncertain", value: Math.max(suspiciousUsers.length, 0), fill: "#c4872f" },
    ],
    activitySeries: syntheticActivity,
    anomalyTypes:
      anomalyTypes.length > 0
        ? anomalyTypes
        : detectorSeed,
    detectorCards: synthesizeDetectorCards(detectorSeed, riskScore, response.summary, locale),
    explainability: buildExplainability(
      anomalyTypes.length > 0
        ? anomalyTypes
        : [
            { type: localizeKnownText("Repeated suspicious users", locale), count: suspiciousUsers.length || 1 },
            { type: localizeKnownText("Autoencoder anomaly score", locale), count: suspiciousCount || 1 },
          ],
      locale
    ),
    suspiciousReviews,
    keyInsights: [
      locale === "ru"
        ? "Режим site-level анализа оценивает пользователей, товары, IP и временные метки, а не только видимый текст отзывов."
        : "Site-level mode evaluates users, items, IPs, and timestamps rather than only page-visible review text.",
      Number(response.summary?.slang_template_cluster_ratio || 0) >= 0.18
        ? locale === "ru"
          ? "Языковой слой нашел повторяющиеся slang-шаблоны в структурированной выборке."
          : "The language layer found repeated slang templates across the structured records sample."
        : Number(response.summary?.slang_domain_confidence || 0) >= 0.35
          ? locale === "ru"
            ? `Language grounding был откалиброван относительно предполагаемого домена ${humanizeDomainLabel(String(response.summary?.slang_domain_label || "general"), locale)}.`
            : `Language grounding was calibrated against the inferred ${humanizeDomainLabel(String(response.summary?.slang_domain_label || "general"), locale)} domain.`
          : locale === "ru"
            ? "Аномальный скор автоэнкодера наиболее силен, когда переданные записи полные и хорошо сформированы."
            : "Autoencoder-based anomaly scoring is strongest when the supplied records are complete and well-formed.",
      slangFlaggedRatings
        ? locale === "ru"
          ? `Пост-хок slang-анализ пометил ${slangFlaggedRatings} записей как hype-heavy или слабо grounded language.`
          : `Post-hoc slang analysis flagged ${slangFlaggedRatings} record(s) for hype-heavy or weakly grounded comment language.`
        : locale === "ru"
          ? "Пост-хок slang-анализ не нашел сильной концентрации hype-heavy language."
          : "Post-hoc slang analysis did not find a strong concentration of hype-heavy comment language.",
      suspiciousUsers.length
        ? locale === "ru"
          ? `Обнаружено ${suspiciousUsers.length} подозрительных user-кластеров в текущем датасете.`
          : `Detected ${suspiciousUsers.length} suspicious user cluster(s) in the current dataset.`
        : locale === "ru"
          ? "Подозрительные user-кластеры в текущем датасете не обнаружены."
          : "No suspicious user clusters were detected in the current dataset.",
    ],
  };
}

export function transformApiResponse(response: ReviewApiResponse, sourceMode: SourceMode, locale: Locale): DashboardResult {
  if (Array.isArray(response.predictions)) {
    return transformRecordsModeResponse(response, locale);
  }
  return transformReviewModeResponse(response, sourceMode, locale);
}

export function getDemoDashboard(mode: SourceMode, locale: Locale) {
  return getDemoResult(mode, locale);
}
