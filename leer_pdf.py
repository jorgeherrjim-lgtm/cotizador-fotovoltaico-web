import fitz


def leer_pdf(ruta_pdf):

    documento = fitz.open(ruta_pdf)

    texto_completo = ""

    for pagina in documento:
        texto_completo += pagina.get_text()

    documento.close()

    return texto_completo