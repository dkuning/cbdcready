import requests
from prometheus_client import Counter, Gauge, Histogram
from cachetools import TTLCache
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("legalDetails")

# === Prometheus метрики ===

# Счётчики
LEGAL_DETAILS_REQUESTS_TOTAL = Counter(
    'legal_details_requests_total',
    'Общее количество запросов по ИНН', labelnames=['result']
)

LEGAL_DETAILS_CACHE_HITS = Counter(
    'legal_details_cache_hits_total',
    'Количество попаданий в кэш'
)

LEGAL_DETAILS_CACHE_MISSES = Counter(
    'legal_details_cache_misses_total',
    'Количество промахов кэша'
)

# Гистограмма времени выполнения
LEGAL_DETAILS_REQUEST_DURATION = Histogram(
    'legal_details_request_duration_seconds',
    'Время выполнения запроса к get_data',
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# Гейджи
LEGAL_DETAILS_CACHE_SIZE = Gauge(
    'legal_details_cache_size',
    'Текущий размер кэша'
)

LEGAL_DETAILS_CACHE_MAX_SIZE = Gauge(
    'legal_details_cache_max_size',
    'Максимальный размер кэша'
)

# Кэш: 1000 записей, TTL = 24 часа
CACHE_MAX_SIZE = 1000
CACHE_TTL_SECONDS = 24 * 60 * 60

cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)
LEGAL_DETAILS_CACHE_MAX_SIZE.set(CACHE_MAX_SIZE)


def get_data(inn):
    """
    Получает данные по ИНН из внешних API.
    Логирует и собирает метрики для Prometheus.
    """
    with LEGAL_DETAILS_REQUEST_DURATION.time():  # Измеряем время
        if not inn or not inn.isdigit() or len(inn) != 10:
            logger.warning(f"Некорректный ИНН: {inn}")
            LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="invalid_inn").inc()
            return {"error": "Некорректный ИНН", "short": {}}

        # Проверка кэша
        if inn in cache:
            LEGAL_DETAILS_CACHE_HITS.inc()
            LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="success").inc()
            logger.info(f"Cache HIT для ИНН: {inn}")
            LEGAL_DETAILS_CACHE_SIZE.set(len(cache))
            return cache[inn]
        else:
            LEGAL_DETAILS_CACHE_MISSES.inc()
            logger.info(f"Cache MISS для ИНН: {inn}")

        # === Запрос к itsoft ===
        url_egrul = f"https://egrul.itsoft.ru/{inn}.json"
        try:
            response = requests.get(url_egrul, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Успешный запрос к itsoft для ИНН: {inn}")
        except Exception as e:
            logger.error(f"Ошибка при запросе к itsoft для ИНН {inn}: {e}")
            if inn in cache:
                LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="fallback_cache").inc()
                LEGAL_DETAILS_CACHE_SIZE.set(len(cache))
                return cache[inn]
            LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="error").inc()
            return {"error": f"Ошибка при запросе к itsoft: {str(e)}", "short": {}}

        # === Обработка данных ===
        short_data = {}
        try:
            св_юл = data.get("СвЮЛ", {})
            short_data["Дата актуальности"] = св_юл.get("@attributes", {}).get("ДатаВып", "-")
            short_data["НаимЮЛПолн"] = св_юл.get("СвНаимЮЛ", {}).get("@attributes", {}).get("НаимЮЛПолн", "-")
            short_data["НаимСокр"] = св_юл.get("СвНаимЮЛ", {}).get("СвНаимЮЛСокр", {}).get("@attributes", {}).get("НаимСокр", "-")

            аттрибуты_св_юл = св_юл.get("@attributes", {})
            short_data["КодОПФ"] = аттрибуты_св_юл.get("КодОПФ", "-")
            short_data["ИНН"] = аттрибуты_св_юл.get("ИНН", "-")
            short_data["КПП"] = аттрибуты_св_юл.get("КПП", "-")
            short_data["ОГРН"] = аттрибуты_св_юл.get("ОГРН", "-")

            дата_обр = св_юл.get("СвОбрЮЛ", {}).get("@attributes", {})
            short_data["ДатаОбр"] = дата_обр.get("ДатаРег") or дата_обр.get("ДатаОГРН", "-")

            адрес_рф = св_юл.get("СвАдресЮЛ", {}).get("АдресРФ", {})
            short_data["КодРегиона"] = адрес_рф.get("@attributes", {}).get("КодРегион", "-")

            оквед_осн = св_юл.get("СвОКВЭД", {}).get("СвОКВЭДОсн", {}).get("@attributes", {})
            short_data["КодОКВЭД"] = оквед_осн.get("КодОКВЭД", "-")

            долж_лица = св_юл.get("СведДолжнФЛ", {})
            долж_лица_фио = (
                долж_лица.get("СвФЛ", {}).get("@attributes", {}).get("Фамилия", "-") + " " +
                долж_лица.get("СвФЛ", {}).get("@attributes", {}).get("Имя", "-") + " " +
                долж_лица.get("СвФЛ", {}).get("@attributes", {}).get("Отчество", "-")
            )
            долж_лица_должность = долж_лица.get("СвДолжн", {}).get("@attributes", {}).get("НаимДолжн", "-")
            долж_лица_инн = долж_лица.get("СвФЛ", {}).get("@attributes", {}).get("ИННФЛ", "-")
            short_data["ЕИО"] = f"{долж_лица_фио} (Должность: {долж_лица_должность}, ИНН: {долж_лица_инн})"

            # === Запрос к Kontur API ===
            url_kontur = "https://services.kontur.ru/calculators/api/codeSearch/codes"
            params = {"inn": inn, "type": "okfs"}
            try:
                response_kontur = requests.post(url_kontur, params=params, timeout=10)
                response_kontur.raise_for_status()
                data_kontur = response_kontur.json()
                logger.info(f"Успешный запрос к Kontur API для ИНН: {inn}")
                requisites = data_kontur.get("data", {}).get("organizationInfo", {}).get("requisites", [])
                for item in requisites:
                    if item.get("id") == "okpo":
                        short_data["ОКПО"] = item.get("content", "-")
                    elif item.get("id") == "okato":
                        short_data["ОКАТО"] = item.get("content", "-")
                    elif item.get("id") == "okfs":
                        short_data["ОКФС"] = item.get("content", "-")
                    elif item.get("id") == "okogu":
                        short_data["ОКОГУ"] = item.get("content", "-")
            except Exception as e:
                logger.warning(f"Ошибка при запросе к Kontur API для ИНН {inn}: {e}")
                if inn in cache:
                    old_short = cache[inn]["short"]
                    for key in ["ОКПО", "ОКАТО", "ОКФС", "ОКОГУ"]:
                        if key in old_short:
                            short_data[key] = old_short[key]
                        else:
                            short_data[key] = "-"
                    logger.info(f"Восстановлены данные из кэша для ИНН: {inn}")
                else:
                    for key in ["ОКПО", "ОКАТО", "ОКФС", "ОКОГУ"]:
                        short_data[key] = "-"
        except Exception as e:
            logger.error(f"Ошибка при обработке данных для ИНН {inn}: {e}")
            LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="error").inc()
            return {"error": f"Ошибка при обработке данных: {str(e)}", "short": {}}

        # Формируем результат
        result = {"data": data, "short": short_data}
        cache[inn] = result
        LEGAL_DETAILS_CACHE_SIZE.set(len(cache))
        LEGAL_DETAILS_REQUESTS_TOTAL.labels(result="success").inc()
        logger.info(f"Данные для ИНН {inn} сохранены в кэш")

        return result