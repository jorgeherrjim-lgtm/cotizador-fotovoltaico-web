import re


MESES = {
    "ENE": "Enero",
    "FEB": "Febrero",
    "MAR": "Marzo",
    "ABR": "Abril",
    "MAY": "Mayo",
    "JUN": "Junio",
    "JUL": "Julio",
    "AGO": "Agosto",
    "SEP": "Septiembre",
    "OCT": "Octubre",
    "NOV": "Noviembre",
    "DIC": "Diciembre"
}


def extraer(texto, patron, flags=0):

    resultado = re.search(
        patron,
        texto,
        flags
    )

    if resultado:
        return resultado.group(1).strip()

    return None


def extraer_historico(texto):

    historico = []

    patron = re.compile(
        r"\b("
        r"ENE|FEB|MAR|ABR|MAY|JUN|"
        r"JUL|AGO|SEP|OCT|NOV|DIC"
        r")\s+"
        r"(\d{2})\s+"
        r"(\d{1,2})\s+"
        r"([\d,]+(?:\.\d+)?)\s+"
        r"([\d,]+(?:\.\d+)?)\s+"
        r"([\d,]+(?:\.\d+)?)\s+"
        r"([\d,]+(?:\.\d+)?)"
    )

    resultados = patron.findall(texto)

    for resultado in resultados:

        mes = resultado[0]
        año = int(resultado[1])

        if año < 50:
            año += 2000
        else:
            año += 1900

        dias = int(resultado[2])

        consumo = float(
            resultado[3].replace(",", "")
        )

        factor_potencia = float(
            resultado[4].replace(",", "")
        )

        consumo_diario = float(
            resultado[5].replace(",", "")
        )

        precio_medio = float(
            resultado[6].replace(",", "")
        )

        historico.append({
            "mes": mes,
            "mes_nombre": MESES.get(mes, mes),
            "año": año,
            "dias": dias,
            "consumo_kwh": consumo,
            "factor_potencia": factor_potencia,
            "consumo_diario": consumo_diario,
            "precio_medio": precio_medio
        })

    return historico