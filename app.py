# ---------------------------------
# BOTON DESCARGAR EXCEL FILTRADO
# ---------------------------------

import io

output = io.BytesIO()

with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df_filtrado.to_excel(writer, index=False, sheet_name='Filtrado')

    workbook = writer.book
    worksheet = writer.sheets['Filtrado']

    # Formatos
    formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy'})
    formato_moneda = workbook.add_format({'num_format': '$#,##0'})

    columnas_fecha = [
        "FECHA_VENCIMIENTO",
        "ULT_FECHA_PAGO",
        "FECHA DE ASIGNACION"
    ]

    columnas_moneda = [
        "VALOR_ULTIMA_FACTURA",
        "ULT_PAGO",
        "DEUDA TOTAL"
    ]

    # Aplicar formato por columna
    for idx, col in enumerate(df_filtrado.columns):
        if col in columnas_fecha:
            worksheet.set_column(idx, idx, 15, formato_fecha)
        if col in columnas_moneda:
            worksheet.set_column(idx, idx, 18, formato_moneda)

output.seek(0)

st.download_button(
    label="📥 Descargar archivo filtrado",
    data=output,
    file_name="resultado_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
