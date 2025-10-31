import requests

def get_data(inn):
    """
    Получает данные по ИНН из внешних API.
    НЕ использует Flask — работает автономно.
    """
    # Проверка ИНН
    if not inn or not inn.isdigit() or len(inn) != 10:
        return {"error": "Некорректный ИНН", "short": {}}

    # === Запрос к itsoft ===
    url_egrul = f"https://egrul.itsoft.ru/{inn}.json"
    try:
        response = requests.get(url_egrul, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {"error": f"Ошибка при запросе к itsoft: {str(e)}", "short": {}}

    # === Обработка кратких данных ===
    short_data = {}
    try:
        св_юл = data.get("СвЮЛ", {})
        аттрибуты_св_юл = св_юл.get("@attributes", {})

        short_data["НаимЮЛПолн"] = св_юл.get("СвНаимЮЛ", {}).get("@attributes", {}).get("НаимЮЛПолн", "-")
        short_data["НаимСокр"] = св_юл.get("СвНаимЮЛ", {}).get("СвНаимЮЛСокр", {}).get("@attributes", {}).get("НаимСокр", "-")
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

        # === Запрос к Kontur API ===
        url_kontur = "https://services.kontur.ru/calculators/api/codeSearch/codes"
        params = {"inn": inn, "type": "okfs"}
        try:
            response_kontur = requests.post(url_kontur, params=params, timeout=10)
            response_kontur.raise_for_status()
            data_kontur = response_kontur.json()

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
            # Если Kontur недоступен — продолжаем с тем, что есть
            short_data["ОКПО"] = "-"
            short_data["ОКАТО"] = "-"
            short_data["ОКФС"] = "-"
            short_data["ОКОГУ"] = "-"
    except Exception as e:
        return {"error": f"Ошибка при обработке данных: {str(e)}", "short": {}}

    return {"data": data, "short": short_data}