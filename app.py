import streamlit as st
import pandas as pd
import io
import plotly.express as px
import random

# Configuración de página
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide")

# Estilo CSS para visibilidad y estética
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #1e2129;
        border: 1px solid #3d4450;
        padding: 15px;
        border-radius: 10px;
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; }
    .stTabs [aria-selected="true"] { background-color: #007bff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Dashboard Ejecutivo - Unidad de Trabajo")
st.subheader("Sistema de Asignación Cruzada (Antiduplicidad)")

# Lista fija de supervisores
SUPERVISORES_NOMINA = [
    "FAVIO ERNESTO VASQUEZ ROMERO",
    "DEGUIN ZOCRATE DEGUIN ZOCRATE",
    "YESID RAFAEL REALES MORENO",
    "ABILIO SEGUNDO ARAUJO ARIÑO",
    "JAVIER DAVID GOMEZ BARRIOS"
]

archivo = st.file_uploader("📂 Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()

    # Limpieza de Deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # ================================
    # SIDEBAR: PANELES DE FILTROS
    # ================================
    st.sidebar.header("🎯 Panel de Filtros")
    
    # Prevenir TypeError con astype(str)
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecnicos_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    with st.sidebar.expander("📍 Filtros de Segmentación", expanded=True):
        rangos_sel = st.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
        sub_sel = st.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
        deuda_minima = st.sidebar.number_input("Deuda mínima ($)", min_value=0, value=100000, step=50000)

    with st.sidebar.expander("👨‍💼 Supervisores"):
        sups_final = st.multiselect("Incluir Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)

    with st.sidebar.expander("👥 Filtro de Operarios", expanded=True):
        #
        modo_exc = st.checkbox("Modo Exclusión (Quitar seleccionados)")
        tecs_sel = st.multiselect("Seleccionar Técnicos para Hoy", tecnicos_disponibles, 
                                  default=tecnicos_disponibles if not modo_exc else [])
        
        tecs_final = [t for t in tecnicos_disponibles if t not in tecs_sel] if modo_exc else tecs_sel

    # ================================
    # LÓGICA DE ASIGNACIÓN CRUZADA
    # ================================
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by="_deuda_num", ascending=False).copy()

    # 1. Asignación Supervisores (Prioridad 1)
    df_supervisores = df_base.head(len(sups_final) * 8).copy()
    if not df_supervisores.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = nombres_sups[:len(df_supervisores)]

    # 2. Asignación Operarios con Intercambio (Prioridad 2)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    
    # Lista para almacenar asignaciones de técnicos
    asignaciones_tecnicos = []
    
    # Diccionario para controlar el límite de 50 por técnico
    conteo_asignacion = {t: 0 for t in tecs_final}
    
    # Iterar sobre las pólizas restantes para intercambiar
    for idx, row in df_restante.iterrows():
        visitante_original = str(row["TECNICOS_INTEGRALES"])
        
        # Buscar técnicos disponibles que NO sean el visitante original y no tengan > 50 pólizas
        candidatos = [t for t in tecs_final if t != visitante_original and conteo_asignacion[t] < 50]
        
        if candidatos:
            # Seleccionar un técnico al azar de los candidatos para mayor rotación
            elegido = random.choice(candidatos)
            conteo_asignacion[elegido] += 1
            
            nueva_fila = row.copy()
            nueva_fila["ASIGNADO_A"] = elegido
            asignaciones_tecnicos.append(nueva_fila)
            
        if all(val >= 50 for val in conteo_asignacion.values()):
            break

    df_tecnicos = pd.DataFrame(asignaciones_tecnicos)

    # ================================
    # PESTAÑAS Y DASHBOARD
    # ================================
    tab_resumen, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_resumen:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Pólizas Cruzadas", f"{len(df_final):,}")
        c2.metric("Cartera Total", f"$ {df_final['_deuda_num'].sum():,.0f}")
        c3.metric("Protección", "Activa ✅")

        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion_Cruzada")
        st.download_button("📥 Descargar Plan de Trabajo", data=output.getvalue(), file_name="seguimiento_cruzado.xlsx")

    with tab_sup:
        st.subheader("Segmentación de Supervisores")
        if not df_supervisores.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.info("📊 Pólizas por Rango de Edad")
                conteo_e_s = df_supervisores["RANGO_EDAD"].astype(str).value_counts().reset_index()
                st.plotly_chart(px.bar(conteo_e_s, x="RANGO_EDAD", y="count", text_auto=True), use_container_width=True)
            with col2:
                st.info("🥧 Deuda por Subcategoría")
                st.plotly_chart(px.pie(df_supervisores, names="SUBCATEGORIA", values="_deuda_num", hole=0.3), use_container_width=True)

    with tab_tec:
        st.subheader("Segmentación de Operarios (Seguimiento Cruzado)")
        if not df_tecnicos.empty:
            col3, col4 = st.columns(2)
            with col3:
                st.info("📊 Pólizas por Rango de Edad")
                conteo_e_t = df_tecnicos["RANGO_EDAD"].astype(str).value_counts().reset_index()
                st.plotly_chart(px.bar(conteo_e_t, x="RANGO_EDAD", y="count", text_auto=True), use_container_width=True)
            with col4:
                st.info("🥧 Composición por Subcategoría")
                conteo_s_t = df_tecnicos["SUBCATEGORIA"].value_counts().reset_index()
                st.plotly_chart(px.pie(conteo_s_t, names="SUBCATEGORIA", values="count", hole=0.3), use_container_width=True)
            
            st.divider()
            st.write("🔄 **Validación de Intercambio:**")
            st.write("El sistema ha verificado que `ASIGNADO_A` sea diferente de `TECNICOS_INTEGRALES` para cada fila.")
        else:
            st.warning("No se pudo realizar el intercambio. Verifique que haya suficientes técnicos diferentes en la lista.")

else:
    st.info("👋 Sube el archivo para iniciar el intercambio de pólizas.")
