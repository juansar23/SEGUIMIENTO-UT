import streamlit as st
import pandas as pd
import io
import plotly.express as px
from datetime import datetime, timedelta

# Configuración inicial
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Unidad de Trabajo")
st.markdown("### Lógica de Asignación: Seguimiento PH vs. Intercambio Operarios")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ================================
    # VALIDAR COLUMNAS CLAVE
    # ================================
    columnas_necesarias = [
        "RANGO_EDAD",
        "SUBCATEGORIA",
        "DEUDA_TOTAL",
        "TECNICOS_INTEGRALES",
        "FECHA_VENCIMIENTO"
    ]

    for col in columnas_necesarias:
        if col not in df.columns:
            st.error(f"❌ No existe la columna: {col}")
            st.stop()

    # ================================
    # PREPARACIÓN DE DATOS Y LÓGICA SEMANAL
    # ================================
    # 1. Limpiar Deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # 2. Lógica de Fechas (Semana Actual)
    df["FECHA_DT"] = pd.to_datetime(df["FECHA_VENCIMIENTO"], errors="coerce")
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)

    # 3. IDENTIFICACIÓN DE UNIDADES Y ESTADO
    df["ES_PH"] = df["TECNICOS_INTEGRALES"].astype(str).str.upper().str.endswith("PH")
    df["SUSPENDIDO_ESTA_SEMANA"] = df["FECHA_DT"] >= inicio_semana

    # =========================================================
    # APLICACIÓN DE LA LÓGICA DE NEGOCIO:
    # - Si termina en PH: Puede repetir (seguimiento a lo suspendido).
    # - Si NO es PH: No visita lo que ya se suspendió esta semana (intercambio).
    # =========================================================
    condicion_final = (df["ES_PH"] == True) | (df["SUSPENDIDO_ESTA_SEMANA"] == False)
    df_base = df[condicion_final].copy()

    # ================================
    # SIDEBAR FILTROS
    # ================================
    st.sidebar.header("🎯 Filtros de Operación")

    rangos = sorted(df_base["RANGO_EDAD"].dropna().astype(str).unique())
    subcategorias = sorted(df_base["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos = sorted(df_base["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", rangos, default=rangos)
    sub_sel = st.sidebar.multiselect("Subcategoría", subcategorias, default=subcategorias)

    deuda_minima = st.sidebar.number_input(
        "Deudas mayores a:",
        min_value=0,
        value=100000,
        step=50000
    )

    st.sidebar.subheader("👥 Selección de Técnicos")
    modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")

    if modo_exclusion:
        excluir = st.sidebar.multiselect("Técnicos a excluir", tecnicos)
        tecnicos_final = [t for t in tecnicos if t not in excluir]
    else:
        tecnicos_final = st.sidebar.multiselect(
            "Técnicos a incluir",
            tecnicos,
            default=tecnicos
        )

    # ================================
    # FILTRADO FINAL Y TOP 50
    # ================================
    df_filtrado = df_base[
        (df_base["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df_base["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df_base["_deuda_num"] >= deuda_minima) &
        (df_base["TECNICOS_INTEGRALES"].astype(str).isin(tecnicos_final))
    ].copy()

    # Ordenar por mayor deuda y limitar a 50 por técnico
    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)
    df_filtrado = (
        df_filtrado
        .groupby("TECNICOS_INTEGRALES")
        .head(50)
        .reset_index(drop=True)
    )

    # Formatear fechas para el usuario final
    columnas_fecha = ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]
    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # ================================
    # INTERFAZ DE USUARIO (TABS)
    # ================================
    tab1, tab2 = st.tabs(["📋 Listado Operativo", "📊 Análisis de Deuda"])

    with tab1:
        st.info(f"💡 Se han procesado las unidades. Las unidades PH mantienen sus suspensiones recientes para seguimiento.")
        st.success(f"Pólizas totales en este reporte: {len(df_filtrado)}")
        
        # Mostrar tabla (quitando columnas auxiliares internas)
        cols_mostrar = [c for c in df_filtrado.columns if not c.startswith(('_', 'ES_PH', 'SUSPENDIDO', 'FECHA_DT'))]
        st.dataframe(df_filtrado[cols_mostrar], use_container_width=True)

        if not df_filtrado.empty:
            output = io.BytesIO()
            df_export = df_filtrado[cols_mostrar].copy()

            # Limpiar formatos de moneda para el Excel final
            columnas_moneda = ["ULT_PAGO", "VALOR_ULTFACT", "DEUDA_TOTAL"]
            for col in columnas_moneda:
                if col in df_export.columns:
                    df_export[col] = pd.to_numeric(
                        df_export[col].astype(str).str.replace(r'[$,.]', '', regex=True), 
                        errors='coerce'
                    ).fillna(0)

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Reporte_Asignacion")
                
                # Formato moneda en Excel
                workbook = writer.book
                worksheet = writer.sheets["Reporte_Asignacion"]
                for col_name in columnas_moneda:
                    if col_name in df_export.columns:
                        idx = df_export.columns.get_loc(col_name) + 1
                        for row in range(2, len(df_export) + 2):
                            worksheet.cell(row=row, column=idx).number_format = '"$"#,##0'

            output.seek(0)
            st.download_button(
                "📥 Descargar Reporte para Operación",
                data=output,
                file_name=f"Reporte_UT_{datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with tab2:
        c1, c2, c3 = st.columns(3)
        c1.metric("Pólizas", len(df_filtrado))
        c2.metric("Cartera Total", f"$ {df_filtrado['_deuda_num'].sum():,.0f}")
        c3.metric("Unidades Activas", df_filtrado["TECNICOS_INTEGRALES"].nunique())

        st.divider()
        
        # Gráfico: Top deudas por técnico
        top_deuda = df_filtrado.groupby("TECNICOS_INTEGRALES")["_deuda_num"].sum().nlargest(10).reset_index()
        fig_deuda = px.bar(top_deuda, x="TECNICOS_INTEGRALES", y="_deuda_num", 
                           title="Top 10 Técnicos por Monto de Cartera",
                           labels={'_deuda_num': 'Deuda Total', 'TECNICOS_INTEGRALES': 'Técnico'})
        st.plotly_chart(fig_deuda, use_container_width=True)

        # Gráfico: PH vs Operarios
        ph_counts = df_filtrado.groupby("TECNICOS_INTEGRALES")["ES_PH"].first().value_counts().reset_index()
        ph_counts["Tipo"] = ph_counts["ES_PH"].map({True: 'PH (Seguimiento)', False: 'Operario (Nuevas)'})
        fig_pie = px.pie(ph_counts, values="count", names="Tipo", title="Distribución de Unidades en el Reporte")
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("👆 Por favor, sube el archivo Excel para procesar las asignaciones según la unidad de trabajo.")
