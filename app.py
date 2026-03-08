import streamlit as st
import pandas as pd
import io
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="Dashboard Intercambio UT", layout="wide")

st.title("📊 Dashboard - Intercambio de Pólizas Suspendidas")
st.markdown("Lógica: Unidades **PH** mantienen seguimiento. Operarios estándar **intercambian** suspensiones.")

archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # 1. Limpieza de Deuda y Fechas
    df["_deuda_num"] = pd.to_numeric(
        df["DEUDA_TOTAL"].astype(str).str.replace(r'[$,.]', '', regex=True), 
        errors="coerce"
    ).fillna(0)

    df["FECHA_DT"] = pd.to_datetime(df["FECHA_VENCIMIENTO"], errors="coerce")
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)

    # Identificar Unidades PH y Suspensiones de la semana
    df["ES_PH"] = df["TECNICOS_INTEGRALES"].astype(str).str.upper().str.endswith("PH")
    df["SUSPENDIDO_ESTA_SEMANA"] = df["FECHA_DT"] >= inicio_semana

    # =========================================================
    # LÓGICA DE INTERCAMBIO CRUZADO (SOLO NO PH)
    # =========================================================
    
    # Separamos las pólizas que deben ser intercambiadas (Operarios No PH con suspensión reciente)
    mask_para_intercambio = (df["ES_PH"] == False) & (df["SUSPENDIDO_ESTA_SEMANA"] == True)
    
    if mask_para_intercambio.any():
        df_intercambio = df[mask_para_intercambio].copy()
        
        # Obtenemos la lista de unidades operativas que entran en el juego de intercambio
        unidades_operativas = df_intercambio["TECNICOS_INTEGRALES"].unique().tolist()
        
        if len(unidades_operativas) > 1:
            # Función para rotar las unidades (el técnico A le da al B, el B al C...)
            def rotar_unidades(unidad_actual):
                idx = unidades_operativas.index(unidad_actual)
                # Pasa a la siguiente unidad en la lista, si es la última vuelve a la primera
                nueva_unidad = unidades_operativas[(idx + 1) % len(unidades_operativas)]
                return nueva_unidad

            df.loc[mask_para_intercambio, "TECNICOS_INTEGRALES"] = df_intercambio["TECNICOS_INTEGRALES"].apply(rotar_unidades)
            st.success(f"🔄 Se han intercambiado {len(df_intercambio)} pólizas entre las unidades operativas estándar.")
        else:
            st.warning("⚠️ Solo hay una unidad operativa estándar; no se puede realizar intercambio cruzado.")
    else:
        st.info("✅ No hay suspensiones recientes en unidades operativas estándar para intercambiar.")

    # =========================================================
    # FILTRADO, ORDEN Y TOP 50
    # =========================================================
    df_base = df.copy()
    
    st.sidebar.header("🎯 Filtros Finales")
    tecnicos = sorted(df_base["TECNICOS_INTEGRALES"].dropna().astype(str).unique())
    tecnicos_sel = st.sidebar.multiselect("Técnicos a Visualizar", tecnicos, default=tecnicos)

    df_filtrado = df_base[df_base["TECNICOS_INTEGRALES"].isin(tecnicos_sel)].copy()
    
    # Ordenar por deuda y limitar a 50 por técnico
    df_filtrado = df_filtrado.sort_values(by="_deuda_num", ascending=False)
    df_filtrado = df_filtrado.groupby("TECNICOS_INTEGRALES").head(50).reset_index(drop=True)

    # Formatear fechas para el reporte
    for col in ["FECHA_VENCIMIENTO", "ULT_FECHAPAGO", "FECHA_ASIGNACION"]:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # ================================
    # VISTAS Y DESCARGA
    # ================================
    tab1, tab2 = st.tabs(["📋 Tabla Intercambiada", "📊 Resumen"])

    with tab1:
        cols_finales = [c for c in df_filtrado.columns if not c.startswith(('_', 'ES_PH', 'SUSPENDIDO', 'FECHA_DT'))]
        st.dataframe(df_filtrado[cols_finales], use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_filtrado[cols_finales].to_excel(writer, index=False)
        output.seek(0)
        
        st.download_button(
            label="📥 Descargar Excel con Intercambio",
            data=output,
            file_name=f"Asignacion_Cruzada_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Pólizas en PH (Sin cambios)", len(df_filtrado[df_filtrado["TECNICOS_INTEGRALES"].str.endswith("PH")]))
        with col2:
            st.metric("Pólizas Intercambiadas", mask_para_intercambio.sum())
        
        fig = px.bar(df_filtrado["TECNICOS_INTEGRALES"].value_counts().reset_index(), 
                     x="TECNICOS_INTEGRALES", y="count", title="Pólizas Finales por Unidad")
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 Sube el archivo Excel para procesar el intercambio de operarios.")
