import math


# ============================================================
# CONVERTIR NÚMERO
# ============================================================

def numero(valor):

    if valor is None:
        return 0

    try:

        if isinstance(valor, str):
            valor = valor.replace(",", "").strip()

        resultado = float(valor)

        if math.isnan(resultado):
            return 0

        return resultado

    except Exception:
        return 0


# ============================================================
# CONVERTIR AÑO
# ============================================================

def convertir_anio(anio):

    try:

        valor = int(anio)

        if valor < 100:
            valor += 2000

        return valor

    except Exception:
        return 0


# ============================================================
# ORDEN DE LOS MESES
# ============================================================

MESES_NUMERO = {

    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12
}


# ============================================================
# DETECTAR PERIODO NOVIEMBRE - OCTUBRE
# ============================================================

def es_periodo_noviembre_octubre(bloque):

    if len(bloque) != 12:
        return False

    meses = []

    for x in bloque:

        codigo = x.get(
            "mes_codigo",
            ""
        )

        if not codigo:

            codigo = x.get(
                "mes",
                ""
            )

        codigo = str(
            codigo
        ).upper()

        # Si viene como nombre completo
        nombres = {

            "ENERO": "ENE",
            "FEBRERO": "FEB",
            "MARZO": "MAR",
            "ABRIL": "ABR",
            "MAYO": "MAY",
            "JUNIO": "JUN",
            "JULIO": "JUL",
            "AGOSTO": "AGO",
            "SEPTIEMBRE": "SEP",
            "OCTUBRE": "OCT",
            "NOVIEMBRE": "NOV",
            "DICIEMBRE": "DIC"
        }

        codigo = nombres.get(
            codigo,
            codigo
        )

        meses.append(
            codigo
        )

    esperado = [

        "NOV",
        "DIC",
        "ENE",
        "FEB",
        "MAR",
        "ABR",
        "MAY",
        "JUN",
        "JUL",
        "AGO",
        "SEP",
        "OCT"
    ]

    return meses == esperado


# ============================================================
# OBTENER LOS 12 MESES PARA EL CÁLCULO
# ============================================================

def obtener_meses_calculo(historico):

    if not historico:

        return []

    ordenado = sorted(

        historico,

        key=lambda x: (

            convertir_anio(
                x.get(
                    "anio",
                    x.get("año", 0)
                )
            ),

            MESES_NUMERO.get(

                str(
                    x.get(
                        "mes_codigo",
                        x.get("mes", "")
                    )
                ).upper(),

                0
            )

        )
    )

    # --------------------------------------------------------
    # SI HAY 13 MESES
    # --------------------------------------------------------

    if len(ordenado) >= 13:

        candidatos = []

        for i in range(
            len(ordenado) - 11
        ):

            bloque = ordenado[
                i:i + 12
            ]

            if es_periodo_noviembre_octubre(
                bloque
            ):

                candidatos.append(
                    bloque
                )

        if candidatos:

            return candidatos[-1]

        return ordenado[-12:]

    # --------------------------------------------------------
    # SI HAY EXACTAMENTE 12
    # --------------------------------------------------------

    if len(ordenado) == 12:

        return ordenado

    # --------------------------------------------------------
    # MENOS DE 12
    # --------------------------------------------------------

    return ordenado


# ============================================================
# CÁLCULO DE BIMESTRES
# ============================================================

def calcular_bimestres(historico):

    if not historico:

        return {

            "valido": False,

            "bimestres": [],

            "promedio_bimestral": 0,

            "promedio_diario": 0,

            "potencia_calculada": 0
        }

    meses_calculo = obtener_meses_calculo(
        historico
    )

    if len(meses_calculo) < 12:

        return {

            "valido": False,

            "bimestres": [],

            "promedio_bimestral": 0,

            "promedio_diario": 0,

            "potencia_calculada": 0
        }

    # --------------------------------------------------------
    # CREAR 6 BIMESTRES
    # --------------------------------------------------------

    bimestres = []

    for i in range(
        0,
        12,
        2
    ):

        mes1 = meses_calculo[i]

        mes2 = meses_calculo[i + 1]

        consumo1 = numero(
            mes1.get(
                "consumo",
                0
            )
        )

        consumo2 = numero(
            mes2.get(
                "consumo",
                0
            )
        )

        consumo_bimestre = (
            consumo1 +
            consumo2
        )

        codigo1 = mes1.get(
            "mes_codigo",
            mes1.get(
                "mes",
                ""
            )
        )

        codigo2 = mes2.get(
            "mes_codigo",
            mes2.get(
                "mes",
                ""
            )
        )

        anio1 = mes1.get(
            "anio",
            mes1.get(
                "año",
                ""
            )
        )

        anio2 = mes2.get(
            "anio",
            mes2.get(
                "año",
                ""
            )
        )

        bimestres.append({

            "numero":
                (i // 2) + 1,

            "periodo":
                f"{codigo1}-{anio1} / "
                f"{codigo2}-{anio2}",

            "mes1":
                codigo1,

            "anio1":
                anio1,

            "mes2":
                codigo2,

            "anio2":
                anio2,

            "consumo":
                consumo_bimestre
        })

    # --------------------------------------------------------
    # SUMA
    # --------------------------------------------------------

    suma_bimestres = sum(

        b["consumo"]

        for b in bimestres
    )

    # --------------------------------------------------------
    # PROMEDIO BIMESTRAL
    # --------------------------------------------------------

    promedio_bimestral = (

        suma_bimestres /
        len(bimestres)

    )

    # --------------------------------------------------------
    # PROMEDIO DIARIO
    #
    # MÉTODO DEL EXCEL
    #
    # Bimestre = 60 días
    # --------------------------------------------------------

    promedio_diario = (

        promedio_bimestral /
        60

    )

    # --------------------------------------------------------
    # POTENCIA CALCULADA
    #
    # MÉTODO DEL EXCEL
    #
    # Consumo diario / 5.5
    #
    # Redondear hacia arriba
    # --------------------------------------------------------

    potencia_calculada = math.ceil(

        promedio_diario /
        5.5

    )

    return {

        "valido":
            True,

        "meses_utilizados":
            meses_calculo,

        "bimestres":
            bimestres,

        "suma_bimestres":
            suma_bimestres,

        "promedio_bimestral":
            promedio_bimestral,

        "promedio_diario":
            promedio_diario,

        "potencia_calculada":
            potencia_calculada
    }


# ============================================================
# COMPATIBILIDAD
#
# Tu app.py utiliza calcular_consumo_normalizado()
# ============================================================

def calcular_consumo_normalizado(
    historico,
    periodicidad="mensual",
    dias=30
):

    if not historico:

        return {

            "valido": False,

            "consumo_total": 0,

            "dias_totales": 0,

            "promedio_mensual": 0,

            "consumo_diario": 0
        }

    meses = obtener_meses_calculo(
        historico
    )

    if not meses:

        return {

            "valido": False,

            "consumo_total": 0,

            "dias_totales": 0,

            "promedio_mensual": 0,

            "consumo_diario": 0
        }

    # --------------------------------------------------------
    # CONSUMO TOTAL
    # --------------------------------------------------------

    consumo_total = sum(

        numero(
            x.get(
                "consumo",
                0
            )
        )

        for x in meses
    )

    # --------------------------------------------------------
    # MENSUAL
    # --------------------------------------------------------

    if periodicidad == "mensual":

        dias_reales = numero(
            dias
        )

        if dias_reales <= 0:

            dias_reales = 30

        promedio_mensual = (

            consumo_total /
            len(meses)

        )

        consumo_diario = (

            promedio_mensual /
            dias_reales

        )

        return {

            "valido":
                True,

            "consumo_total":
                consumo_total,

            "dias_totales":
                dias_reales,

            "dias":
                dias_reales,

            "promedio_mensual":
                promedio_mensual,

            "consumo_diario":
                consumo_diario
        }

    # --------------------------------------------------------
    # BIMESTRAL
    # --------------------------------------------------------

    else:

        dias_reales = numero(
            dias
        )

        if dias_reales <= 0:

            dias_reales = 60

        promedio_bimestral = (

            consumo_total /
            6

        )

        consumo_diario = (

            promedio_bimestral /
            dias_reales

        )

        return {

            "valido":
                True,

            "consumo_total":
                consumo_total,

            "dias_totales":
                dias_reales,

            "dias":
                dias_reales,

            "promedio_bimestral":
                promedio_bimestral,

            "consumo_diario":
                consumo_diario
        }


# ============================================================
# COMPATIBILIDAD
#
# Si alguna parte del proyecto utiliza calcular_normalizado()
# también seguirá funcionando.
# ============================================================

def calcular_normalizado(
    historico,
    periodicidad="mensual",
    dias=30
):

    return calcular_consumo_normalizado(
        historico,
        periodicidad,
        dias
    )


# ============================================================
# DIMENSIONAMIENTO SOLAR
# ============================================================

def calcular_potencia_solar(
    consumo_diario,
    hsp
):

    consumo_diario = numero(
        consumo_diario
    )

    hsp = numero(
        hsp
    )

    if (
        consumo_diario <= 0
        or
        hsp <= 0
    ):

        return 0

    return (
        consumo_diario /
        hsp
    )


# ============================================================
# DIMENSIONAMIENTO DE PANELES
#
# FÓRMULA DEL EXCEL:
#
# =REDONDEAR.MAS((B22*1000/C24),0)
#
# B22 = Potencia del sistema en kW
# C24 = Potencia del panel en W
# ============================================================

def calcular_paneles(
    potencia_kw,
    potencia_panel_w=585
):

    potencia_kw = numero(
        potencia_kw
    )

    potencia_panel_w = numero(
        potencia_panel_w
    )

    if (
        potencia_kw <= 0
        or
        potencia_panel_w <= 0
    ):

        return {

            "valido": False,

            "potencia_sistema_kw": 0,

            "potencia_panel_w": 0,

            "numero_paneles": 0,

            "potencia_instalada_kw": 0,

            "excedente_kw": 0,

            "inversores": 0
        }

    # --------------------------------------------------------
    # NO. DE PANELES
    #
    # Excel:
    #
    # =REDONDEAR.MAS(
    #     (B22*1000/C24),
    #     0
    # )
    # --------------------------------------------------------

    numero_paneles = math.ceil(

        (
            potencia_kw *
            1000
        )
        /
        potencia_panel_w

    )

    # --------------------------------------------------------
    # POTENCIA INSTALADA
    #
    # Excel:
    #
    # =(B25*C24)/1000
    # --------------------------------------------------------

    potencia_instalada_kw = (

        numero_paneles *
        potencia_panel_w
    ) / 1000

    # --------------------------------------------------------
    # EXCEDENTE
    # --------------------------------------------------------

    excedente_kw = (

        potencia_instalada_kw -
        potencia_kw
    )

    # --------------------------------------------------------
    # INVERSOR
    #
    # Para la propuesta actual:
    # 1 inversor
    # --------------------------------------------------------

    inversores = 1

    return {

        "valido":
            True,

        "potencia_sistema_kw":
            potencia_kw,

        "potencia_panel_w":
            potencia_panel_w,

        "numero_paneles":
            numero_paneles,

        "potencia_instalada_kw":
            potencia_instalada_kw,

        "excedente_kw":
            excedente_kw,

        "inversores":
            inversores
    }


# ============================================================
# OPCIONES DE PANELES
#
# Permite comparar diferentes potencias de panel.
# ============================================================

def calcular_opciones_paneles(
    potencia_kw,
    paneles=None
):

    if paneles is None:

        paneles = [

            550,
            585,
            600,
            620,
            650
        ]

    potencia_kw = numero(
        potencia_kw
    )

    opciones = []

    if potencia_kw <= 0:

        return opciones

    for potencia_panel_w in paneles:

        potencia_panel_w = numero(
            potencia_panel_w
        )

        if potencia_panel_w <= 0:
            continue

        # ----------------------------------------------------
        # NÚMERO DE PANELES
        # ----------------------------------------------------

        numero_paneles = math.ceil(

            (
                potencia_kw *
                1000
            )
            /
            potencia_panel_w

        )

        # ----------------------------------------------------
        # POTENCIA INSTALADA
        # ----------------------------------------------------

        potencia_instalada_kw = (

            numero_paneles *
            potencia_panel_w

        ) / 1000

        # ----------------------------------------------------
        # EXCEDENTE
        # ----------------------------------------------------

        excedente_kw = (

            potencia_instalada_kw -
            potencia_kw
        )

        opciones.append({

            "potencia_panel_w":
                int(potencia_panel_w),

            "numero_paneles":
                numero_paneles,

            "cantidad":
                numero_paneles,

            "potencia_instalada_kw":
                potencia_instalada_kw,

            "potencia_total_kwp":
                potencia_instalada_kw,

            "excedente_kw":
                excedente_kw,

            "exceso_kw":
                excedente_kw,

            "inversores":
                1,

            "recomendada":
                False
        })

    # --------------------------------------------------------
    # RECOMENDADA
    #
    # Por ahora se selecciona la opción con menor excedente.
    # --------------------------------------------------------

    if opciones:

        menor = min(

            opciones,

            key=lambda x:
                x["excedente_kw"]
        )

        menor["recomendada"] = True

    return opciones