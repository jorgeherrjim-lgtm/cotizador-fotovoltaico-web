from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import fitz
import re
import math
import io
from datetime import datetime

from calculos import (
    calcular_bimestres,
    calcular_consumo_normalizado,
    calcular_potencia_solar,
    calcular_paneles,
    calcular_opciones_paneles
)

from hsp import (
    HSP_POR_ESTADO,
    obtener_hsp
)

# ============================================================
# REPORTLAB
# ============================================================

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

app = Flask(__name__)

app.secret_key = "cotizador-fotovoltaico-2026"


# ============================================================
# LEER PDF
# ============================================================

def extraer_texto_pdf(archivo):

    contenido = archivo.read()

    documento = fitz.open(
        stream=contenido,
        filetype="pdf"
    )

    texto = ""

    for pagina in documento:

        texto += (
            pagina.get_text()
            + "\n"
        )

    paginas = len(documento)

    documento.close()

    return texto, paginas


# ============================================================
# CONVERTIR NÚMERO
# ============================================================

def convertir_numero(valor):

    if not valor:
        return 0

    valor = str(valor)

    valor = valor.replace(",", "")

    try:

        return float(valor)

    except ValueError:

        return 0


# ============================================================
# DATOS DEL RECIBO
# ============================================================

def extraer_datos_recibo(texto):

    datos = {}

    patrones = {

        "servicio":
            r"NO\.\s*DE\s*SERVICIO:\s*([0-9]+)",

        "tarifa":
            r"TARIFA\??:\s*([A-Z0-9]+)",

        "carga":
            r"CARGA\s+CONECTADA\s*kW:\s*([\d,.]+)",

        "demanda_contratada":
            r"DEMANDA\s+CONTRATADA\s*kW:\s*([\d,.]+)",

        "medidor":
            r"NO\.\s*MEDIDOR:\s*([A-Z0-9]+)",

        "periodo":
            r"PERIODO\s+FACTURADO:\s*([^\n]+)",

        "total":
            r"TOTAL\s+A\s+PAGAR:\s*\$?\s*([\d,.]+)"
    }

    for nombre, patron in patrones.items():

        resultado = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if resultado:

            valor = (
                resultado
                .group(1)
                .strip()
            )

            if nombre in [
                "carga",
                "demanda_contratada",
                "total"
            ]:

                valor = convertir_numero(
                    valor
                )

            datos[nombre] = valor

    return datos


# ============================================================
# HISTÓRICO DEL RECIBO
# ============================================================

def extraer_historico(texto):

    meses = {

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

    patron = re.compile(

        r"\b("
        r"ENE|FEB|MAR|ABR|MAY|JUN|"
        r"JUL|AGO|SEP|OCT|NOV|DIC"
        r")\s+"

        r"(\d{2})\s+"

        r"(\d+)\s+"

        r"([\d,.]+)\s+"

        r"([\d,.]+)\s+"

        r"([\d,.]+)\s+"

        r"([\d,.]+)",

        re.IGNORECASE
    )

    encontrados = patron.findall(
        texto
    )

    historico = []

    vistos = set()

    for registro in encontrados:

        codigo_mes = (
            registro[0]
            .upper()
        )

        anio = int(
            registro[1]
        )

        if anio < 50:

            anio += 2000

        else:

            anio += 1900

        dias = int(
            registro[2]
        )

        consumo = convertir_numero(
            registro[3]
        )

        factor_potencia = convertir_numero(
            registro[4]
        )

        consumo_diario = convertir_numero(
            registro[5]
        )

        precio_medio = convertir_numero(
            registro[6]
        )

        clave = (
            codigo_mes,
            anio
        )

        if clave in vistos:

            continue

        vistos.add(
            clave
        )

        historico.append({

            "mes":
                meses[codigo_mes],

            "mes_codigo":
                codigo_mes,

            "anio":
                anio,

            "año":
                anio,

            "dias":
                dias,

            "consumo":
                consumo,

            "factor_potencia":
                factor_potencia,

            "consumo_diario":
                consumo_diario,

            "precio_medio":
                precio_medio
        })

    return historico


# ============================================================
# INICIO
# ============================================================

@app.route("/")
def inicio():

    return render_template(
        "inicio.html"
    )


# ============================================================
# PROCESAR PDF
# ============================================================

def procesar_pdf():

    print(
        "\n========== NUEVO PDF =========="
    )

    print(
        "Archivos recibidos:",
        list(
            request.files.keys()
        )
    )

    print(
        "Formularios recibidos:",
        list(
            request.form.keys()
        )
    )

    archivo = None

    # --------------------------------------------------------
    # BUSCAR ARCHIVO "pdf"
    # --------------------------------------------------------

    if "pdf" in request.files:

        archivo = request.files[
            "pdf"
        ]

    # --------------------------------------------------------
    # SI NO EXISTE, TOMAR CUALQUIER ARCHIVO
    # --------------------------------------------------------

    elif len(request.files) > 0:

        archivo = next(
            iter(
                request.files.values()
            )
        )

    # --------------------------------------------------------
    # SIN ARCHIVO
    # --------------------------------------------------------

    if archivo is None:

        print(
            "NO LLEGÓ NINGÚN ARCHIVO"
        )

        return """

        <h1>
            No se recibió ningún archivo PDF.
        </h1>

        <p>
            El navegador no está enviando el archivo.
        </p>

        <a href="/">
            Regresar
        </a>

        """

    print(
        "Archivo recibido:",
        archivo.filename
    )

    # --------------------------------------------------------
    # NOMBRE VACÍO
    # --------------------------------------------------------

    if archivo.filename == "":

        return """

        <h1>
            No seleccionaste ningún archivo.
        </h1>

        <a href="/">
            Regresar
        </a>

        """

    # --------------------------------------------------------
    # VALIDAR PDF
    # --------------------------------------------------------

    if not archivo.filename.lower().endswith(
        ".pdf"
    ):

        return """

        <h1>
            El archivo no es PDF.
        </h1>

        <a href="/">
            Regresar
        </a>

        """

    # --------------------------------------------------------
    # LEER PDF
    # --------------------------------------------------------

    try:

        texto, paginas = extraer_texto_pdf(
            archivo
        )

    except Exception as error:

        print(
            "ERROR LEYENDO PDF:",
            error
        )

        return f"""

        <h1>
            Error leyendo el PDF
        </h1>

        <p>
            {error}
        </p>

        <a href="/">
            Regresar
        </a>

        """

    # --------------------------------------------------------
    # EXTRAER DATOS
    # --------------------------------------------------------

    datos = extraer_datos_recibo(
        texto
    )

    historico = extraer_historico(
        texto
    )

    print(
        "Páginas:",
        paginas
    )

    print(
        "Histórico encontrado:",
        len(historico)
    )

    # --------------------------------------------------------
    # GUARDAR EN SESIÓN
    # --------------------------------------------------------

    session[
        "datos_recibo"
    ] = datos

    session[
        "historico"
    ] = historico

    session[
        "paginas"
    ] = paginas

    session[
        "nombre_archivo"
    ] = archivo.filename

    # --------------------------------------------------------
    # LIMPIAR DATOS DE CÁLCULOS ANTERIORES
    # --------------------------------------------------------

    session.pop(
        "historico_seleccionado",
        None
    )

    session.pop(
        "estado",
        None
    )

    session.pop(
        "hsp",
        None
    )

    session.pop(
        "cotizacion",
        None
    )

    # --------------------------------------------------------
    # CONTINUAR
    # --------------------------------------------------------

    return redirect(
        url_for(
            "mostrar_recibo"
        )
    )


# ============================================================
# RUTA /CARGAR
# ============================================================

@app.route(
    "/cargar",
    methods=["POST"]
)
def cargar():

    return procesar_pdf()


# ============================================================
# RUTA /LEER_PDF
# ============================================================

@app.route(
    "/leer_pdf",
    methods=["POST"]
)
def leer_pdf():

    return procesar_pdf()


# ============================================================
# MOSTRAR RECIBO
# ============================================================

@app.route("/recibo")
def mostrar_recibo():

    datos = session.get(
        "datos_recibo"
    )

    historico = session.get(
        "historico"
    )

    paginas = session.get(
        "paginas"
    )

    archivo = session.get(
        "nombre_archivo"
    )

    if datos is None:

        return redirect(
            url_for(
                "inicio"
            )
        )

    return render_template(

        "resultado_pdf.html",

        datos=datos,

        historico=historico,

        paginas=paginas,

        archivo=archivo
    )


# ============================================================
# SELECCIONAR MESES
# ============================================================

@app.route(
    "/seleccionar_meses",
    methods=["GET", "POST"]
)
def seleccionar_meses():

    historico = session.get(
        "historico"
    )

    if not historico:

        return redirect(
            url_for(
                "inicio"
            )
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == "POST":

        indices = request.form.getlist(
            "meses"
        )

        if len(indices) != 12:

            return render_template(

                "seleccionar_meses.html",

                historico=historico,

                error=(
                    "Debes seleccionar exactamente "
                    "12 meses."
                )
            )

        seleccionados = []

        try:

            for indice in indices:

                indice = int(
                    indice
                )

                seleccionados.append(
                    historico[indice]
                )

        except Exception as error:

            print(
                "ERROR SELECCIONANDO MESES:",
                error
            )

            return render_template(

                "seleccionar_meses.html",

                historico=historico,

                error=(
                    "Ocurrió un problema "
                    "al seleccionar los meses."
                )
            )

        # ----------------------------------------------------
        # GUARDAR SELECCIÓN
        # ----------------------------------------------------

        session[
            "historico_seleccionado"
        ] = seleccionados

        # ----------------------------------------------------
        # IR AL ESTADO
        # ----------------------------------------------------

        return redirect(
            url_for(
                "seleccionar_estado"
            )
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(

        "seleccionar_meses.html",

        historico=historico
    )


# ============================================================
# SELECCIONAR ESTADO
# ============================================================

@app.route(
    "/seleccionar_estado",
    methods=["GET", "POST"]
)
def seleccionar_estado():

    historico = session.get(
        "historico_seleccionado"
    )

    if not historico:

        return redirect(
            url_for(
                "seleccionar_meses"
            )
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == "POST":

        estado = request.form.get(
            "estado"
        )

        if not estado:

            return render_template(

                "seleccionar_estado.html",

                estados=HSP_POR_ESTADO,

                error=(
                    "Selecciona un estado."
                )
            )

        hsp = obtener_hsp(
            estado
        )

        if hsp is None:

            return render_template(

                "seleccionar_estado.html",

                estados=HSP_POR_ESTADO,

                error=(
                    "No se encontró HSP "
                    "para ese estado."
                )
            )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        session[
            "estado"
        ] = estado

        session[
            "hsp"
        ] = hsp

        # ----------------------------------------------------
        # IR A CÁLCULOS
        # ----------------------------------------------------

        return redirect(
            url_for(
                "calcular"
            )
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(

        "seleccionar_estado.html",

        estados=HSP_POR_ESTADO
    )


# ============================================================
# CÁLCULO
# ============================================================

@app.route("/calcular")
def calcular():

    historico = session.get(
        "historico_seleccionado"
    )

    estado = session.get(
        "estado"
    )

    hsp = session.get(
        "hsp"
    )

    if not historico:

        return redirect(
            url_for(
                "inicio"
            )
        )

    if not estado or not hsp:

        return redirect(
            url_for(
                "seleccionar_estado"
            )
        )

    # --------------------------------------------------------
    # BIMESTRES
    # --------------------------------------------------------

    resultado_bimestres = (
        calcular_bimestres(
            historico
        )
    )

    # --------------------------------------------------------
    # NORMALIZADO
    # --------------------------------------------------------

    normalizado = (
        calcular_consumo_normalizado(
            historico
        )
    )

    # --------------------------------------------------------
    # POTENCIA SOLAR
    # --------------------------------------------------------

    potencia_solar = (
        calcular_potencia_solar(

            normalizado[
                "consumo_diario"
            ],

            hsp
        )
    )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    resultado = {

        "bimestres":
            resultado_bimestres[
                "bimestres"
            ],

        "promedio_bimestral":
            resultado_bimestres[
                "promedio_bimestral"
            ],

        "promedio_diario_bimestral":
            resultado_bimestres[
                "promedio_diario"
            ],

        "potencia_calculada":
            resultado_bimestres[
                "potencia_calculada"
            ],

        "consumo_total":
            normalizado[
                "consumo_total"
            ],

        "dias_totales":
            normalizado[
                "dias_totales"
            ],

        "promedio_mensual":
            normalizado[
                "promedio_mensual"
            ],

        "consumo_diario":
            normalizado[
                "consumo_diario"
            ],

        "potencia_solar":
            potencia_solar
    }

    return render_template(

        "calculo.html",

        resultado=resultado,

        estado=estado,

        hsp=hsp
    )


# ============================================================
# PANELES Y CALCULADORA DE COTIZACIÓN
# ============================================================

@app.route("/paneles")
def paneles():

    historico = session.get(
        "historico_seleccionado"
    )

    estado = session.get(
        "estado"
    )

    hsp = session.get(
        "hsp"
    )

    # --------------------------------------------------------
    # VALIDAR SESIÓN
    # --------------------------------------------------------

    if not historico:

        return redirect(
            url_for(
                "inicio"
            )
        )

    if not estado or not hsp:

        return redirect(
            url_for(
                "seleccionar_estado"
            )
        )

    # --------------------------------------------------------
    # CONSUMO NORMALIZADO
    # --------------------------------------------------------

    normalizado = (
        calcular_consumo_normalizado(
            historico
        )
    )

    consumo_diario = (
        normalizado[
            "consumo_diario"
        ]
    )

    # --------------------------------------------------------
    # POTENCIA SOLAR
    # --------------------------------------------------------

    potencia_solar = (
        calcular_potencia_solar(

            consumo_diario,

            hsp
        )
    )

    # --------------------------------------------------------
    # RESULTADO DE BIMESTRES
    # --------------------------------------------------------

    resultado_bimestres = (
        calcular_bimestres(
            historico
        )
    )

    # --------------------------------------------------------
    # POTENCIA DEL SISTEMA
    # --------------------------------------------------------

    potencia_sistema = (
        resultado_bimestres[
            "potencia_calculada"
        ]
    )

    # --------------------------------------------------------
    # PANEL PRINCIPAL
    # --------------------------------------------------------

    potencia_panel = 585

    # --------------------------------------------------------
    # CÁLCULO DE PANELES
    # --------------------------------------------------------

    propuesta = calcular_paneles(

        potencia_sistema,

        potencia_panel
    )

    # --------------------------------------------------------
    # OPCIONES DE PANELES
    # --------------------------------------------------------

    potencias_paneles = [

        550,
        585,
        600,
        620,
        650

    ]

    opciones_paneles = (
        calcular_opciones_paneles(

            potencia_sistema,

            potencias_paneles
        )
    )

    # ========================================================
    # DATOS PARA LA CALCULADORA
    # ========================================================

    tipo_cambio = 19.18

    # --------------------------------------------------------
    # DATOS DEL PANEL POR DEFECTO
    # --------------------------------------------------------

    cotizacion_panel = {

        "marca": "",

        "modelo": "",

        "potencia_w":
            potencia_panel,

        "precio_usd":
            0,

        "precio_mxn":
            0,

        "cantidad":
            propuesta.get(
                "cantidad",
                propuesta.get(
                    "numero_paneles",
                    0
                )
            ),

        "total":
            0
    }

    # --------------------------------------------------------
    # DATOS DEL INVERSOR POR DEFECTO
    # --------------------------------------------------------

    cotizacion_inversor = {

        "marca": "",

        "modelo": "",

        "potencia_kw":
            0,

        "precio_usd":
            0,

        "precio_mxn":
            0,

        "cantidad":
            1,

        "total":
            0
    }

    # ========================================================
    # ENVIAR A PANELES.HTML
    # ========================================================

    return render_template(

        "paneles.html",

        estado=estado,

        hsp=hsp,

        consumo_diario=consumo_diario,

        potencia_solar=potencia_solar,

        potencia_sistema=potencia_sistema,

        potencia_panel=potencia_panel,

        propuesta=propuesta,

        opciones_paneles=opciones_paneles,

        potencias_paneles=potencias_paneles,

        tipo_cambio=tipo_cambio,

        cotizacion_panel=cotizacion_panel,

        cotizacion_inversor=cotizacion_inversor
    )


# ============================================================
# CALCULADORA DE COTIZACIÓN
# ============================================================

@app.route(
    "/calcular_cotizacion",
    methods=["POST"]
)
def calcular_cotizacion():

    try:

        # ====================================================
        # DATOS DEL PANEL
        # ====================================================

        marca_panel = request.form.get(
            "marca_panel",
            ""
        ).strip()

        modelo_panel = request.form.get(
            "modelo_panel",
            ""
        ).strip()

        potencia_panel = convertir_numero(
            request.form.get(
                "potencia_panel",
                0
            )
        )

        precio_panel_usd = convertir_numero(
            request.form.get(
                "precio_panel_usd",
                0
            )
        )

        # ====================================================
        # DATOS DEL INVERSOR
        # ====================================================

        marca_inversor = request.form.get(
            "marca_inversor",
            ""
        ).strip()

        modelo_inversor = request.form.get(
            "modelo_inversor",
            ""
        ).strip()

        precio_inversor_usd = convertir_numero(
            request.form.get(
                "precio_inversor_usd",
                0
            )
        )

        potencia_inversor = convertir_numero(
            request.form.get(
                "potencia_inversor",
                0
            )
        )

        # ====================================================
        # TIPO DE CAMBIO
        # ====================================================

        tipo_cambio = convertir_numero(
            request.form.get(
                "tipo_cambio",
                19.18
            )
        )

        if tipo_cambio <= 0:

            tipo_cambio = 19.18

        # ====================================================
        # POTENCIA DEL SISTEMA
        # ====================================================

        historico = session.get(
            "historico_seleccionado"
        )

        if not historico:

            return redirect(
                url_for(
                    "inicio"
                )
            )

        resultado_bimestres = (
            calcular_bimestres(
                historico
            )
        )

        potencia_sistema = convertir_numero(

            resultado_bimestres[
                "potencia_calculada"
            ]
        )

        # ====================================================
        # CANTIDAD DE PANELES
        # ====================================================

        if potencia_panel > 0:

            cantidad_paneles = math.ceil(

                (
                    potencia_sistema
                    * 1000
                )
                / potencia_panel

            )

        else:

            cantidad_paneles = 0

        # ====================================================
        # POTENCIA INSTALADA
        # ====================================================

        potencia_instalada = (

            cantidad_paneles
            * potencia_panel
            / 1000

        )

        # ====================================================
        # EXCEDENTE
        # ====================================================

        excedente = (

            potencia_instalada
            - potencia_sistema

        )

        # ====================================================
        # PRECIO PANEL MXN
        # ====================================================

        precio_panel_mxn = (

            precio_panel_usd
            * tipo_cambio

        )

        # ====================================================
        # TOTAL PANELES
        # ====================================================

        total_paneles = (

            cantidad_paneles
            * precio_panel_mxn

        )

        # ====================================================
        # POTENCIA TOTAL DEL ARREGLO
        # ====================================================

        potencia_arreglo = (
            potencia_instalada
        )

        # ====================================================
        # CANTIDAD DE INVERSORES
        # ====================================================

        if potencia_inversor > 0:

            cantidad_inversores = math.ceil(

                potencia_arreglo
                / potencia_inversor

            )

        else:

            cantidad_inversores = 0

        # ====================================================
        # PRECIO INVERSOR MXN
        # ====================================================

        precio_inversor_mxn = (

            precio_inversor_usd
            * tipo_cambio

        )

        # ====================================================
        # TOTAL INVERSORES
        # ====================================================

        total_inversores = (

            cantidad_inversores
            * precio_inversor_mxn

        )

        # ====================================================
        # TOTAL GENERAL
        # ====================================================

        total_general = (

            total_paneles
            + total_inversores

        )

        # ====================================================
        # GUARDAR COTIZACIÓN
        # ====================================================

        cotizacion = {

            "tipo_cambio":
                tipo_cambio,

            "potencia_sistema":
                potencia_sistema,

            # ----------------------------------------------
            # PANEL
            # ----------------------------------------------

            "panel": {

                "marca":
                    marca_panel,

                "modelo":
                    modelo_panel,

                "potencia_w":
                    potencia_panel,

                "cantidad":
                    cantidad_paneles,

                "potencia_instalada":
                    potencia_instalada,

                "excedente":
                    excedente,

                "precio_usd":
                    precio_panel_usd,

                "precio_mxn":
                    precio_panel_mxn,

                "total":
                    total_paneles
            },

            # ----------------------------------------------
            # INVERSOR
            # ----------------------------------------------

            "inversor": {

                "marca":
                    marca_inversor,

                "modelo":
                    modelo_inversor,

                "potencia_kw":
                    potencia_inversor,

                "cantidad":
                    cantidad_inversores,

                "precio_usd":
                    precio_inversor_usd,

                "precio_mxn":
                    precio_inversor_mxn,

                "total":
                    total_inversores
            },

            # ----------------------------------------------
            # TOTAL
            # ----------------------------------------------

            "total":
                total_general
        }

        session[
            "cotizacion"
        ] = cotizacion

        # ====================================================
        # RECUPERAR DATOS
        # ====================================================

        estado = session.get(
            "estado"
        )

        hsp = session.get(
            "hsp"
        )

        normalizado = (
            calcular_consumo_normalizado(
                historico
            )
        )

        consumo_diario = (
            normalizado[
                "consumo_diario"
            ]
        )

        potencia_solar = (
            calcular_potencia_solar(

                consumo_diario,

                hsp
            )
        )

        propuesta = calcular_paneles(

            potencia_sistema,

            potencia_panel
        )

        potencias_paneles = [

            550,
            585,
            600,
            620,
            650

        ]

        opciones_paneles = (
            calcular_opciones_paneles(

                potencia_sistema,

                potencias_paneles
            )
        )

        # ====================================================
        # MOSTRAR RESULTADO
        # ====================================================

        return render_template(

            "paneles.html",

            estado=estado,

            hsp=hsp,

            consumo_diario=consumo_diario,

            potencia_solar=potencia_solar,

            potencia_sistema=potencia_sistema,

            potencia_panel=potencia_panel,

            propuesta=propuesta,

            opciones_paneles=opciones_paneles,

            potencias_paneles=potencias_paneles,

            tipo_cambio=tipo_cambio,

            cotizacion_panel=cotizacion.get(
                "panel"
            ),

            cotizacion_inversor=cotizacion.get(
                "inversor"
            ),

            cotizacion=cotizacion
        )

    except Exception as error:

        print(
            "ERROR CALCULANDO COTIZACIÓN:"
        )

        print(
            error
        )

        return f"""

        <h1>
            Error al calcular la cotización
        </h1>

        <p>
            {error}
        </p>

        <br>

        <a href="/paneles">
            Regresar a paneles
        </a>

        """


# ============================================================
# FUNCIONES PARA PDF
# ============================================================

def dinero(valor):

    valor = convertir_numero(valor)

    return "${:,.2f} MXN".format(
        valor
    )


def numero_pdf(valor, decimales=2):

    valor = convertir_numero(valor)

    return "{:,.{}f}".format(
        valor,
        decimales
    )


# ============================================================
# PIE DE PÁGINA DEL PDF
# ============================================================

def pie_pdf(canvas, doc):

    canvas.saveState()

    ancho, alto = letter

    # --------------------------------------------------------
    # LÍNEA
    # --------------------------------------------------------

    canvas.setStrokeColor(
        colors.HexColor("#D9D9D9")
    )

    canvas.line(
        18 * mm,
        15 * mm,
        ancho - 18 * mm,
        15 * mm
    )

    # --------------------------------------------------------
    # TEXTO
    # --------------------------------------------------------

    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.setFillColor(
        colors.HexColor("#666666")
    )

    canvas.drawString(
        18 * mm,
        10 * mm,
        "Cotización de sistema fotovoltaico"
    )

    canvas.drawRightString(
        ancho - 18 * mm,
        10 * mm,
        f"Página {doc.page}"
    )

    canvas.restoreState()


# ============================================================
# GENERAR PDF DE COTIZACIÓN
# ============================================================

@app.route(
    "/generar_pdf",
    methods=["GET"]
)
def generar_pdf():

    try:

        # ====================================================
        # RECUPERAR DATOS DE SESIÓN
        # ====================================================

        cotizacion = session.get(
            "cotizacion"
        )

        historico = session.get(
            "historico_seleccionado"
        )

        datos_recibo = session.get(
            "datos_recibo",
            {}
        )

        estado = session.get(
            "estado",
            ""
        )

        hsp = session.get(
            "hsp",
            0
        )

        nombre_archivo = session.get(
            "nombre_archivo",
            ""
        )

        # ====================================================
        # VALIDAR
        # ====================================================

        if not historico:

            return redirect(
                url_for(
                    "inicio"
                )
            )

        if not cotizacion:

            return redirect(
                url_for(
                    "paneles"
                )
            )

        # ====================================================
        # VOLVER A CALCULAR INFORMACIÓN
        # ====================================================

        resultado_bimestres = (
            calcular_bimestres(
                historico
            )
        )

        normalizado = (
            calcular_consumo_normalizado(
                historico
            )
        )

        consumo_diario = (
            normalizado[
                "consumo_diario"
            ]
        )

        potencia_solar = (
            calcular_potencia_solar(

                consumo_diario,

                hsp
            )
        )

        potencia_sistema = convertir_numero(

            cotizacion.get(
                "potencia_sistema",
                0
            )
        )

        panel = cotizacion.get(
            "panel",
            {}
        )

        inversor = cotizacion.get(
            "inversor",
            {}
        )

        tipo_cambio = convertir_numero(

            cotizacion.get(
                "tipo_cambio",
                19.18
            )
        )

        # ====================================================
        # DATOS DEL CLIENTE
        # ====================================================

        cliente = session.get(
            "cliente",
            {}
        )

        nombre_cliente = cliente.get(
            "nombre",
            "Cliente"
        )

        telefono_cliente = cliente.get(
            "telefono",
            ""
        )

        correo_cliente = cliente.get(
            "correo",
            ""
        )

        direccion_cliente = cliente.get(
            "direccion",
            ""
        )

        # ====================================================
        # NÚMERO DE COTIZACIÓN
        # ====================================================

        numero_cotizacion = session.get(
            "numero_cotizacion"
        )

        if not numero_cotizacion:

            numero_cotizacion = (
                "COT-"
                + datetime.now().strftime(
                    "%Y%m%d-%H%M"
                )
            )

            session[
                "numero_cotizacion"
            ] = numero_cotizacion

        fecha = datetime.now().strftime(
            "%d/%m/%Y"
        )

        # ====================================================
        # CREAR PDF EN MEMORIA
        # ====================================================

        buffer = io.BytesIO()

        documento = SimpleDocTemplate(

            buffer,

            pagesize=letter,

            rightMargin=18 * mm,

            leftMargin=18 * mm,

            topMargin=18 * mm,

            bottomMargin=20 * mm
        )

        # ====================================================
        # ESTILOS
        # ====================================================

        estilos = getSampleStyleSheet()

        titulo = ParagraphStyle(

            "Titulo",

            parent=estilos["Title"],

            fontName="Helvetica-Bold",

            fontSize=22,

            leading=26,

            alignment=TA_CENTER,

            textColor=colors.HexColor(
                "#123B5D"
            ),

            spaceAfter=10
        )

        subtitulo = ParagraphStyle(

            "Subtitulo",

            parent=estilos["Normal"],

            fontName="Helvetica",

            fontSize=10,

            leading=14,

            alignment=TA_CENTER,

            textColor=colors.HexColor(
                "#666666"
            ),

            spaceAfter=20
        )

        h1 = ParagraphStyle(

            "H1",

            parent=estilos["Heading1"],

            fontName="Helvetica-Bold",

            fontSize=16,

            leading=20,

            textColor=colors.HexColor(
                "#123B5D"
            ),

            spaceBefore=8,

            spaceAfter=10
        )

        h2 = ParagraphStyle(

            "H2",

            parent=estilos["Heading2"],

            fontName="Helvetica-Bold",

            fontSize=12,

            leading=15,

            textColor=colors.HexColor(
                "#1F5E82"
            ),

            spaceBefore=6,

            spaceAfter=8
        )

        normal = ParagraphStyle(

            "NormalPDF",

            parent=estilos["Normal"],

            fontName="Helvetica",

            fontSize=9,

            leading=13,

            textColor=colors.HexColor(
                "#333333"
            )
        )

        pequeño = ParagraphStyle(

            "Pequeno",

            parent=normal,

            fontSize=7.5,

            leading=10
        )

        centrado = ParagraphStyle(

            "Centrado",

            parent=normal,

            alignment=TA_CENTER
        )

        derecha = ParagraphStyle(

            "Derecha",

            parent=normal,

            alignment=TA_RIGHT
        )

        total_style = ParagraphStyle(

            "Total",

            parent=normal,

            fontName="Helvetica-Bold",

            fontSize=16,

            leading=20,

            textColor=colors.HexColor(
                "#123B5D"
            ),

            alignment=TA_RIGHT
        )

        # ====================================================
        # CONTENIDO
        # ====================================================

        elementos = []

        # ====================================================
        # PORTADA
        # ====================================================

        elementos.append(
            Spacer(
                1,
                25 * mm
            )
        )

        elementos.append(
            Paragraph(
                "COTIZACIÓN",
                titulo
            )
        )

        elementos.append(
            Paragraph(
                "Sistema fotovoltaico",
                subtitulo
            )
        )

        datos_portada = [

            [
                Paragraph(
                    "<b>No. de cotización</b>",
                    normal
                ),

                Paragraph(
                    numero_cotizacion,
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Fecha</b>",
                    normal
                ),

                Paragraph(
                    fecha,
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Cliente</b>",
                    normal
                ),

                Paragraph(
                    nombre_cliente,
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Estado</b>",
                    normal
                ),

                Paragraph(
                    str(estado),
                    normal
                )
            ]

        ]

        tabla_portada = Table(

            datos_portada,

            colWidths=[
                55 * mm,
                100 * mm
            ]
        )

        tabla_portada.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    colors.HexColor(
                        "#B8C7D1"
                    )
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#D9D9D9"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                )

            ])
        )

        elementos.append(
            tabla_portada
        )

        elementos.append(
            Spacer(
                1,
                20 * mm
            )
        )

        elementos.append(
            Paragraph(
                "Propuesta de dimensionamiento y suministro de sistema fotovoltaico.",
                centrado
            )
        )

        elementos.append(
            Spacer(
                1,
                8 * mm
            )
        )

        elementos.append(
            Paragraph(
                "Documento generado automáticamente a partir del análisis del consumo eléctrico proporcionado.",
                pequeño
            )
        )

        elementos.append(
            PageBreak()
        )

        # ====================================================
        # INFORMACIÓN DEL CLIENTE
        # ====================================================

        elementos.append(
            Paragraph(
                "1. Información del cliente",
                h1
            )
        )

        datos_cliente = [

            [
                Paragraph(
                    "<b>Cliente</b>",
                    normal
                ),
                Paragraph(
                    nombre_cliente or "-",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Teléfono</b>",
                    normal
                ),
                Paragraph(
                    telefono_cliente or "-",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Correo</b>",
                    normal
                ),
                Paragraph(
                    correo_cliente or "-",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Dirección</b>",
                    normal
                ),
                Paragraph(
                    direccion_cliente or "-",
                    normal
                )
            ]

        ]

        tabla_cliente = Table(

            datos_cliente,

            colWidths=[
                40 * mm,
                115 * mm
            ]
        )

        tabla_cliente.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#F2F5F7"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor(
                        "#DDDDDD"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        elementos.append(
            tabla_cliente
        )

        # ====================================================
        # RESUMEN DEL SISTEMA
        # ====================================================

        elementos.append(
            Paragraph(
                "2. Resumen del sistema",
                h1
            )
        )

        resumen_sistema = [

            [
                Paragraph(
                    "<b>Estado</b>",
                    normal
                ),

                Paragraph(
                    str(estado),
                    normal
                ),

                Paragraph(
                    "<b>HSP</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(hsp, 2)
                    + " h/día",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Consumo total</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        normalizado[
                            "consumo_total"
                        ],
                        2
                    )
                    + " kWh",
                    normal
                ),

                Paragraph(
                    "<b>Consumo diario</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        consumo_diario,
                        2
                    )
                    + " kWh/día",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Potencia calculada</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        potencia_sistema,
                        2
                    )
                    + " kW",
                    normal
                ),

                Paragraph(
                    "<b>Potencia solar</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        potencia_solar,
                        2
                    )
                    + " kWp",
                    normal
                )
            ]

        ]

        tabla_resumen = Table(

            resumen_sistema,

            colWidths=[
                42 * mm,
                40 * mm,
                42 * mm,
                36 * mm
            ]
        )

        tabla_resumen.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),

                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor(
                        "#DDDDDD"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        elementos.append(
            tabla_resumen
        )

        # ====================================================
        # HISTÓRICO MENSUAL
        # ====================================================

        elementos.append(
            Spacer(
                1,
                8 * mm
            )
        )

        elementos.append(
            Paragraph(
                "3. Histórico de consumo utilizado",
                h1
            )
        )

        datos_historico = [

            [
                Paragraph(
                    "<b>Mes</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Año</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Días</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Consumo kWh</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>kWh/día</b>",
                    pequeño
                )

            ]

        ]

        for mes in historico:

            datos_historico.append([

                Paragraph(
                    str(
                        mes.get(
                            "mes_codigo",
                            mes.get(
                                "mes",
                                ""
                            )
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    str(
                        mes.get(
                            "anio",
                            mes.get(
                                "año",
                                ""
                            )
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    str(
                        mes.get(
                            "dias",
                            0
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        mes.get(
                            "consumo",
                            0
                        ),
                        2
                    ),
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        mes.get(
                            "consumo_diario",
                            0
                        ),
                        2
                    ),
                    pequeño
                )

            ])

        tabla_historico = Table(

            datos_historico,

            colWidths=[
                30 * mm,
                25 * mm,
                25 * mm,
                40 * mm,
                40 * mm
            ],

            repeatRows=1
        )

        tabla_historico.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#123B5D"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                )

            ])
        )

        elementos.append(
            tabla_historico
        )

        # ====================================================
        # BIMESTRES
        # ====================================================

        elementos.append(
            Spacer(
                1,
                8 * mm
            )
        )

        elementos.append(
            Paragraph(
                "4. Análisis bimestral",
                h1
            )
        )

        datos_bimestres = [

            [
                Paragraph(
                    "<b>Bimestre</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Periodo</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Consumo</b>",
                    pequeño
                )

            ]

        ]

        for bimestre in resultado_bimestres.get(
            "bimestres",
            []
        ):

            datos_bimestres.append([

                Paragraph(
                    str(
                        bimestre.get(
                            "numero",
                            ""
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    str(
                        bimestre.get(
                            "periodo",
                            ""
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        bimestre.get(
                            "consumo",
                            0
                        ),
                        2
                    )
                    + " kWh",
                    pequeño
                )

            ])

        tabla_bimestres = Table(

            datos_bimestres,

            colWidths=[
                30 * mm,
                80 * mm,
                50 * mm
            ],

            repeatRows=1
        )

        tabla_bimestres.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F5E82"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                )

            ])
        )

        elementos.append(
            tabla_bimestres
        )

        # ====================================================
        # MÉTRICAS
        # ====================================================

        elementos.append(
            Spacer(
                1,
                5 * mm
            )
        )

        metricas = [

            [
                Paragraph(
                    "<b>Promedio bimestral</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        resultado_bimestres.get(
                            "promedio_bimestral",
                            0
                        ),
                        2
                    )
                    + " kWh",
                    derecha
                )
            ],

            [
                Paragraph(
                    "<b>Promedio diario</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        resultado_bimestres.get(
                            "promedio_diario",
                            0
                        ),
                        2
                    )
                    + " kWh/día",
                    derecha
                )
            ],

            [
                Paragraph(
                    "<b>Potencia calculada</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        resultado_bimestres.get(
                            "potencia_calculada",
                            0
                        ),
                        2
                    )
                    + " kW",
                    derecha
                )
            ]

        ]

        tabla_metricas = Table(

            metricas,

            colWidths=[
                90 * mm,
                70 * mm
            ]
        )

        tabla_metricas.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#F2F5F7"
                    )
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor(
                        "#DDDDDD"
                    )
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )

        elementos.append(
            tabla_metricas
        )

        elementos.append(
            PageBreak()
        )

        # ====================================================
        # DISEÑO DEL SISTEMA
        # ====================================================

        elementos.append(
            Paragraph(
                "5. Diseño del sistema fotovoltaico",
                h1
            )
        )

        elementos.append(
            Paragraph(
                "La siguiente propuesta se obtiene a partir de la potencia calculada y la configuración de panel seleccionada.",
                normal
            )
        )

        elementos.append(
            Spacer(
                1,
                5 * mm
            )
        )

        datos_sistema = [

            [
                Paragraph(
                    "<b>Concepto</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Resultado</b>",
                    pequeño
                )

            ],

            [
                Paragraph(
                    "Potencia requerida",
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        potencia_sistema,
                        2
                    )
                    + " kW",
                    pequeño
                )
            ],

            [
                Paragraph(
                    "Panel seleccionado",
                    pequeño
                ),

                Paragraph(
                    (
                        str(
                            panel.get(
                                "marca",
                                ""
                            )
                        )
                        + " "
                        +
                        str(
                            panel.get(
                                "modelo",
                                ""
                            )
                        )
                    ).strip()
                    or "Panel seleccionado",
                    pequeño
                )
            ],

            [
                Paragraph(
                    "Potencia por panel",
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        panel.get(
                            "potencia_w",
                            0
                        ),
                        0
                    )
                    + " W",
                    pequeño
                )
            ],

            [
                Paragraph(
                    "Número de paneles",
                    pequeño
                ),

                Paragraph(
                    str(
                        panel.get(
                            "cantidad",
                            0
                        )
                    ),
                    pequeño
                )
            ],

            [
                Paragraph(
                    "Potencia instalada",
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        panel.get(
                            "potencia_instalada",
                            0
                        ),
                        3
                    )
                    + " kW",
                    pequeño
                )
            ],

            [
                Paragraph(
                    "Excedente",
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        panel.get(
                            "excedente",
                            0
                        ),
                        3
                    )
                    + " kW",
                    pequeño
                )
            ]

        ]

        tabla_sistema = Table(

            datos_sistema,

            colWidths=[
                70 * mm,
                90 * mm
            ],

            repeatRows=1
        )

        tabla_sistema.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#123B5D"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "BACKGROUND",
                    (0, 1),
                    (0, -1),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        elementos.append(
            tabla_sistema
        )

        # ====================================================
        # INVERSOR
        # ====================================================

        elementos.append(
            Spacer(
                1,
                8 * mm
            )
        )

        elementos.append(
            Paragraph(
                "6. Inversor",
                h1
            )
        )

        nombre_inversor = (

            str(
                inversor.get(
                    "marca",
                    ""
                )
            )
            + " "
            +
            str(
                inversor.get(
                    "modelo",
                    ""
                )
            )

        ).strip()

        if not nombre_inversor:

            nombre_inversor = (
                "Inversor no especificado"
            )

        datos_inversor = [

            [
                Paragraph(
                    "<b>Marca / modelo</b>",
                    normal
                ),

                Paragraph(
                    nombre_inversor,
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Potencia</b>",
                    normal
                ),

                Paragraph(
                    numero_pdf(
                        inversor.get(
                            "potencia_kw",
                            0
                        ),
                        2
                    )
                    + " kW",
                    normal
                )
            ],

            [
                Paragraph(
                    "<b>Cantidad</b>",
                    normal
                ),

                Paragraph(
                    str(
                        inversor.get(
                            "cantidad",
                            0
                        )
                    ),
                    normal
                )
            ]

        ]

        tabla_inversor = Table(

            datos_inversor,

            colWidths=[
                55 * mm,
                105 * mm
            ]
        )

        tabla_inversor.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#F2F5F7"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor(
                        "#DDDDDD"
                    )
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        elementos.append(
            tabla_inversor
        )

        # ====================================================
        # COMPARATIVA
        # ====================================================

        elementos.append(
            PageBreak()
        )

        elementos.append(
            Paragraph(
                "7. Comparación de paneles",
                h1
            )
        )

        potencias_comparacion = [

            550,
            585,
            600,
            620,
            650

        ]

        opciones = calcular_opciones_paneles(

            potencia_sistema,

            potencias_comparacion
        )

        datos_opciones = [

            [
                Paragraph(
                    "<b>Panel</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Cantidad</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Instalado</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Excedente</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Estado</b>",
                    pequeño
                )

            ]

        ]

        for opcion in opciones:

            recomendada = opcion.get(
                "recomendada",
                False
            )

            datos_opciones.append([

                Paragraph(
                    numero_pdf(
                        opcion.get(
                            "potencia_panel_w",
                            0
                        ),
                        0
                    )
                    + " W",
                    pequeño
                ),

                Paragraph(
                    str(
                        opcion.get(
                            "numero_paneles",
                            0
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        opcion.get(
                            "potencia_instalada_kw",
                            0
                        ),
                        3
                    )
                    + " kW",
                    pequeño
                ),

                Paragraph(
                    numero_pdf(
                        opcion.get(
                            "excedente_kw",
                            0
                        ),
                        3
                    )
                    + " kW",
                    pequeño
                ),

                Paragraph(
                    "RECOMENDADA"
                    if recomendada
                    else "-",
                    pequeño
                )

            ])

        tabla_opciones = Table(

            datos_opciones,

            colWidths=[
                28 * mm,
                28 * mm,
                35 * mm,
                35 * mm,
                34 * mm
            ],

            repeatRows=1
        )

        tabla_opciones.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#123B5D"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )

        elementos.append(
            tabla_opciones
        )

        # ====================================================
        # COTIZACIÓN ECONÓMICA
        # ====================================================

        elementos.append(
            Spacer(
                1,
                10 * mm
            )
        )

        elementos.append(
            Paragraph(
                "8. Cotización económica",
                h1
            )
        )

        elementos.append(
            Paragraph(
                "Los precios se presentan considerando el tipo de cambio utilizado al momento de elaborar la propuesta.",
                normal
            )
        )

        elementos.append(
            Spacer(
                1,
                5 * mm
            )
        )

        # ----------------------------------------------------
        # PANEL
        # ----------------------------------------------------

        elementos.append(
            Paragraph(
                "Paneles solares",
                h2
            )
        )

        nombre_panel = (

            str(
                panel.get(
                    "marca",
                    ""
                )
            )
            + " "
            +
            str(
                panel.get(
                    "modelo",
                    ""
                )
            )

        ).strip()

        if not nombre_panel:

            nombre_panel = (
                "Panel solar"
            )

        datos_panel_precio = [

            [
                Paragraph(
                    "<b>Descripción</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Cantidad</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Precio USD</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Precio MXN</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Subtotal</b>",
                    pequeño
                )

            ],

            [

                Paragraph(
                    nombre_panel
                    + "<br/>"
                    + numero_pdf(
                        panel.get(
                            "potencia_w",
                            0
                        ),
                        0
                    )
                    + " W",
                    pequeño
                ),

                Paragraph(
                    str(
                        panel.get(
                            "cantidad",
                            0
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    "$"
                    + numero_pdf(
                        panel.get(
                            "precio_usd",
                            0
                        ),
                        2
                    ),
                    pequeño
                ),

                Paragraph(
                    "$"
                    + numero_pdf(
                        panel.get(
                            "precio_mxn",
                            0
                        ),
                        2
                    ),
                    pequeño
                ),

                Paragraph(
                    dinero(
                        panel.get(
                            "total",
                            0
                        )
                    ),
                    pequeño
                )

            ]

        ]

        tabla_panel_precio = Table(

            datos_panel_precio,

            colWidths=[
                48 * mm,
                24 * mm,
                29 * mm,
                29 * mm,
                30 * mm
            ],

            repeatRows=1
        )

        tabla_panel_precio.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F5E82"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "ALIGN",
                    (1, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )

        elementos.append(
            tabla_panel_precio
        )

        # ----------------------------------------------------
        # INVERSOR
        # ----------------------------------------------------

        elementos.append(
            Spacer(
                1,
                6 * mm
            )
        )

        elementos.append(
            Paragraph(
                "Inversor",
                h2
            )
        )

        datos_inversor_precio = [

            [
                Paragraph(
                    "<b>Descripción</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Cantidad</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Precio USD</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Precio MXN</b>",
                    pequeño
                ),

                Paragraph(
                    "<b>Subtotal</b>",
                    pequeño
                )

            ],

            [

                Paragraph(
                    nombre_inversor
                    + "<br/>"
                    + numero_pdf(
                        inversor.get(
                            "potencia_kw",
                            0
                        ),
                        2
                    )
                    + " kW",
                    pequeño
                ),

                Paragraph(
                    str(
                        inversor.get(
                            "cantidad",
                            0
                        )
                    ),
                    pequeño
                ),

                Paragraph(
                    "$"
                    + numero_pdf(
                        inversor.get(
                            "precio_usd",
                            0
                        ),
                        2
                    ),
                    pequeño
                ),

                Paragraph(
                    "$"
                    + numero_pdf(
                        inversor.get(
                            "precio_mxn",
                            0
                        ),
                        2
                    ),
                    pequeño
                ),

                Paragraph(
                    dinero(
                        inversor.get(
                            "total",
                            0
                        )
                    ),
                    pequeño
                )

            ]

        ]

        tabla_inversor_precio = Table(

            datos_inversor_precio,

            colWidths=[
                48 * mm,
                24 * mm,
                29 * mm,
                29 * mm,
                30 * mm
            ],

            repeatRows=1
        )

        tabla_inversor_precio.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F5E82"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "ALIGN",
                    (1, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )

        elementos.append(
            tabla_inversor_precio
        )

        # ====================================================
        # TIPO DE CAMBIO
        # ====================================================

        elementos.append(
            Spacer(
                1,
                5 * mm
            )
        )

        tipo_cambio_tabla = Table([

            [

                Paragraph(
                    "<b>Tipo de cambio utilizado</b>",
                    normal
                ),

                Paragraph(
                    "$"
                    + numero_pdf(
                        tipo_cambio,
                        2
                    )
                    + " MXN/USD",
                    derecha
                )

            ]

        ], colWidths=[90 * mm, 70 * mm])

        tipo_cambio_tabla.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor(
                        "#F2F5F7"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#CCCCCC"
                    )
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        elementos.append(
            tipo_cambio_tabla
        )

        # ====================================================
        # TOTAL
        # ====================================================

        elementos.append(
            Spacer(
                1,
                8 * mm
            )
        )

        total_tabla = Table([

            [

                Paragraph(
                    "TOTAL DE LA PROPUESTA",
                    h2
                ),

                Paragraph(
                    dinero(
                        cotizacion.get(
                            "total",
                            0
                        )
                    ),
                    total_style
                )

            ]

        ], colWidths=[85 * mm, 75 * mm])

        total_tabla.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    1,
                    colors.HexColor(
                        "#123B5D"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                )

            ])
        )

        elementos.append(
            total_tabla
        )

        # ====================================================
        # CONDICIONES
        # ====================================================

        elementos.append(
            PageBreak()
        )

        elementos.append(
            Paragraph(
                "9. Consideraciones de la propuesta",
                h1
            )
        )

        condiciones = [

            "La presente propuesta se basa en la información de consumo disponible en el recibo eléctrico proporcionado.",

            "El dimensionamiento puede requerir ajustes después de realizar una visita técnica al sitio.",

            "Los precios utilizados corresponden a los valores capturados en la calculadora de cotización.",

            "El tipo de cambio utilizado se muestra explícitamente en este documento.",

            "La disponibilidad de equipos y precios puede cambiar de acuerdo con los proveedores.",

            "La instalación, estructura, protecciones eléctricas, cableado, mano de obra y otros conceptos deberán confirmarse de acuerdo con el alcance final del proyecto.",

            "La propuesta deberá ser revisada y aprobada antes de proceder con la adquisición o instalación del sistema."

        ]

        for condicion in condiciones:

            elementos.append(

                Paragraph(
                    "• " + condicion,
                    normal
                )

            )

            elementos.append(
                Spacer(
                    1,
                    3 * mm
                )
            )

        # ====================================================
        # FIRMA
        # ====================================================

        elementos.append(
            Spacer(
                1,
                18 * mm
            )
        )

        firma = Table([

            [

                Paragraph(
                    "<b>Cliente</b>",
                    centrado
                ),

                Paragraph(
                    "<b>Asesor / Empresa</b>",
                    centrado
                )

            ],

            [

                Paragraph(
                    "______________________________",
                    centrado
                ),

                Paragraph(
                    "______________________________",
                    centrado
                )

            ],

            [

                Paragraph(
                    nombre_cliente or "Nombre y firma",
                    centrado
                ),

                Paragraph(
                    "Nombre y firma",
                    centrado
                )

            ],

            [

                Paragraph(
                    "Fecha: __________________",
                    centrado
                ),

                Paragraph(
                    "Fecha: __________________",
                    centrado
                )

            ]

        ], colWidths=[80 * mm, 80 * mm])

        firma.setStyle(

            TableStyle([

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )

        elementos.append(
            firma
        )

        # ====================================================
        # INFORMACIÓN DEL ARCHIVO ORIGINAL
        # ====================================================

        elementos.append(
            Spacer(
                1,
                15 * mm
            )
        )

        elementos.append(

            Paragraph(

                "Documento generado automáticamente por el sistema de dimensionamiento fotovoltaico.",

                pequeño

            )

        )

        if nombre_archivo:

            elementos.append(

                Paragraph(

                    "Archivo de origen: "
                    + str(
                        nombre_archivo
                    ),

                    pequeño

                )

            )

        # ====================================================
        # GENERAR
        # ====================================================

        documento.build(

            elementos,

            onFirstPage=pie_pdf,

            onLaterPages=pie_pdf
        )

        buffer.seek(0)

        # ====================================================
        # NOMBRE DEL PDF
        # ====================================================

        nombre_pdf = (

            "Cotizacion_"
            + numero_cotizacion
            + ".pdf"
        )

        return send_file(

            buffer,

            mimetype="application/pdf",

            as_attachment=True,

            download_name=nombre_pdf
        )

    except Exception as error:

        print(
            "\n========== ERROR GENERANDO PDF =========="
        )

        print(
            error
        )

        return f"""

        <h1>
            Error generando la cotización PDF
        </h1>

        <p>
            {error}
        </p>

        <br>

        <a href="/paneles">
            Regresar a paneles
        </a>

        """


# ============================================================
# DATOS DEL CLIENTE PARA LA COTIZACIÓN
# ============================================================

@app.route(
    "/guardar_cliente",
    methods=["POST"]
)
def guardar_cliente():

    session[
        "cliente"
    ] = {

        "nombre":
            request.form.get(
                "nombre",
                ""
            ).strip(),

        "telefono":
            request.form.get(
                "telefono",
                ""
            ).strip(),

        "correo":
            request.form.get(
                "correo",
                ""
            ).strip(),

        "direccion":
            request.form.get(
                "direccion",
                ""
            ).strip()
    }

    return redirect(
        url_for(
            "paneles"
        )
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )