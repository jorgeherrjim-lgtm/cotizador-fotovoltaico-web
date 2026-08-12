# ============================================================
# HSP DE REFERENCIA POR ESTADO
# ============================================================

HSP_POR_ESTADO = {

    "Aguascalientes": 5.60,
    "Baja California": 5.50,
    "Baja California Sur": 5.70,
    "Campeche": 5.10,
    "Chiapas": 4.90,
    "Chihuahua": 5.59,
    "Ciudad de México": 5.00,
    "Coahuila": 5.50,
    "Colima": 5.20,
    "Durango": 5.73,
    "Estado de México": 5.00,
    "Guanajuato": 5.30,
    "Guerrero": 5.30,
    "Hidalgo": 5.10,
    "Jalisco": 5.30,
    "Michoacán": 5.30,
    "Morelos": 5.30,
    "Nayarit": 5.60,
    "Nuevo León": 5.40,
    "Oaxaca": 5.50,
    "Puebla": 5.10,
    "Querétaro": 5.30,
    "Quintana Roo": 5.20,
    "San Luis Potosí": 5.40,
    "Sinaloa": 5.98,
    "Sonora": 5.73,
    "Tabasco": 4.80,
    "Tamaulipas": 5.30,
    "Tlaxcala": 5.10,
    "Veracruz": 4.90,
    "Yucatán": 5.20,
    "Zacatecas": 5.60
}


# ============================================================
# COMPATIBILIDAD CON APP.PY Y HTML
# ============================================================

# IMPORTANTE:
# El archivo seleccionar_estado.html utiliza:
#
# estados.items()
#
# Por eso HSP_ESTADOS debe ser un diccionario,
# no una lista.

HSP_ESTADOS = HSP_POR_ESTADO


# ============================================================
# OBTENER HSP
# ============================================================

def obtener_hsp(estado):

    if not estado:
        return None

    return HSP_POR_ESTADO.get(
        estado
    )


# ============================================================
# OBTENER ESTADOS
# ============================================================

def obtener_estados():

    return list(
        HSP_POR_ESTADO.keys()
    )