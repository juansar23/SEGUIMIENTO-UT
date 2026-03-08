import streamlit as st
import pandas as pd
import io
import plotly.express as px
from datetime import datetime, timedelta
import random

st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Sistema de Intercambio")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # ================================
    # PREPARACIÓN Y LIMPIEZA
    # ================================
    df["_deuda_num"] = pd.to_numeric(
        df["DEUDA_TOTAL"].astype(str).str.replace(r'[$,.]', '', regex=True), 
        errors="coerce"
    ).fillna(0)

    df["FECHA_DT"] = pd.to_datetime(df["FECHA_VENCIMIENTO"], errors="coerce")
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)

    # Identificar Unidades
    df["ES_PH"] = df["TECNICOS_INTEGRALES"].astype(str).str.upper().str.endswith("PH")
    df["SUSPENDIDO_ESTA_SEMANA"] = df["FECHA_DT"] >= inicio_semana

    # =========================================================
    # LÓGICA DE INTERCAMBIO (REASIGNACIÓN)
    # =========================================================
    
    # 1. Pólizas que deben salir de los operarios (fueron suspendidas esta semana)
    mask_intercambio = (df["ES_PH"] == False) & (df["SUSPENDIDO_ESTA_SEMANA"] == True)
    
    # 2. Obtener lista de técnicos PH disponibles para recibir el intercambio
    tecnicos_ph = df[df["ES_PH"] == True]["TECNICOS_INTEGRALES"].unique().tolist()

    if tecnicos_ph:
        # Reasignamos esas pólizas a un técnico PH aleatorio (o podrías definir un orden)
        df.loc[mask_intercambio, "TECNICOS_INTEGRALES"] = [
            random.choice(tecnicos_ph) for _ in range(mask_intercambio.sum())
        ]
        st.success(f"✅ Se han intercambiado {mask_intercambio.sum()} pólizas de operarios hacia unidades PH.")
    else:
        st.warning("⚠️ No se encontraron unidades PH para recibir el intercambio.")

    # El df_base ahora ya tiene las pólizas reasignadas
    df_base = df.copy()

    # ================================
    # SIDEBAR FILTROS
    # ================================
    st.sidebar.header("🎯 Filtros")
    tecnicos = sorted(df_base["TECNICOS_INTEGRALES"].dropna().astype(str).unique())
    tecnicos_final = st.sidebar.multiselect("Técnicos", tecnicos, default=tecnicos)

    # ================================
    # FILTRADO Y TOP 50
    # ================================
    df_filtrado = df_base[df_base["TECNICOS_INTEGRALES"].isin(tecnicos_final)].copy()
    
    # Aplicar orden y límite de 50 por técnico (incluyendo lo reasignado)
    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)
    df_filtrado = df_filtrado.groupby("TECNICOS_INTEGRALES").head(50).reset_index(drop=True)

    # Formatear fechas para visualización
    columnas_fecha = ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]
    for col in columnas_fecha:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # ================================
    # INTERFAZ (TABS)
    # ================================
    tab1, tab2 = st.tabs(["📋 Listado Operativo", "📊 Resumen"])

    with tab1:
        cols_mostrar = [c for c in df_filtrado.columns if not c.startswith(('_', 'ES_PH', 'SUSPENDIDO', 'FECHA_DT'))]
        st.dataframe(df_filtrado[cols_mostrar], use_container_width=True)

        # Descarga Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_filtrado[cols_mostrar].to_excel(writer, index=False)
        output.seek(0)
        st.download_button("📥 Descargar Excel Intercambiado", data=output, file_name="asignacion_final.xlsx")

    with tab2:
        st.metric("Pólizas Reasignadas a PH", mask_intercambio.sum())
        conteo_ut = df_filtrado["TECNICOS_INTEGRALES"].value_counts().reset_index()
        fig = px.bar(conteo_ut, x="TECNICOS_INTEGRALES", y="count", title="Pólizas por Unidad (Post-Intercambio)")
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 Sube el archivo para ejecutar la reasignación automática.")
