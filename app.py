import streamlit as st
import pandas as pd
import io
import plotly.express as px

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

st.title("🚀 Asignación por Barrios - Unidad de Trabajo")
st.subheader("Optimización de Ruta y Seguimiento Cruzado")

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

    # Identificar columna de barrio (ajustar si el nombre exacto varía)
    col_barrio = "BARRIO" if "BARRIO" in df.columns else "NOMBRE_BARRIO"
    if col_barrio not in df.columns:
        st.warning("⚠️ No se encontró la columna 'BARRIO'. La asignación será individual.")

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
    # LÓGICA DE ASIGNACIÓN POR BARRIO
    # ================================
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].sort_values(by=["_deuda_num"], ascending=False).copy()

    # 1. Asignación Supervisores (Individual por Deuda Alta)
    df_supervisores = df_base.head(len(sups_final) * 8).copy()
    if not df_supervisores.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_supervisores["ASIGNADO_A"] = nombres_sups[:len(df_supervisores)]

    # 2. Asignación Operarios (Agrupada por Barrio)
    df_restante = df_base.drop(df_supervisores.index) if not df_supervisores.empty else df_base
    
    # Agrupar el inventario sobrante por barrio
    barrios_agrupados = df_restante.groupby(col_barrio)
    
    asignaciones_tecnicos = []
    conteo_asignacion = {t: 0 for t in tecs_final}
    
    # Priorizar barrios con más pólizas para asignarlos completos
    barrios_ordenados = sorted(barrios_agrupados, key=lambda x: len(x[1]), reverse=True)

    for nombre_barrio, datos_barrio in barrios_ordenados:
        # Filtrar operarios que no visitaron este barrio (o la mayoría de él)
        # y que aún tengan cupo
        for tecnico in tecs_final:
            cupo_disponible = 50 - conteo_asignacion[tecnico]
            
            if cupo_disponible > 0:
                # Verificar que el técnico no sea el visitante predominante de este barrio
                visitante_principal = datos_barrio["TECNICOS_INTEGRALES"].mode().iloc[0] if not datos_barrio.empty else ""
                
                if tecnico != visitante_principal:
                    # Tomar lo que quepa en el cupo del técnico de este barrio
                    a_asignar = datos_barrio.head(cupo_disponible).copy()
                    a_asignar["ASIGNADO_A"] = tecnico
                    asignaciones_tecnicos.append(a_asignar)
                    
                    conteo_asignacion[tecnico] += len(a_asignar)
                    # Quitar las pólizas ya asignadas del barrio actual
                    datos_barrio = datos_barrio.drop(a_asignar.index)
            
            if datos_barrio.empty:
                break

    df_tecnicos = pd.concat(asignaciones_tecnicos) if asignaciones_tecnicos else pd.DataFrame()

    # ================================
    # DASHBOARD
    # ================================
    tab_resumen, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    with tab_resumen:
        df_final = pd.concat([df_supervisores, df_tecnicos], ignore_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Pólizas Asignadas", f"{len(df_final):,}")
        c2.metric("Cartera Gestionada", f"$ {df_final['_deuda_num'].sum():,.0f}")
        c3.metric("Zonificación", "Agrupada por Barrio 🏠")

        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Asignacion_Zonificada")
        st.download_button("📥 Descargar Reporte por Barrio", data=output.getvalue(), file_name="asignacion_barrios.xlsx")

    with tab_sup:
        if not df_supervisores.empty:
            st.info("📊 Pólizas por Rango de Edad (Supervisores)")
            st.plotly_chart(px.bar(df_supervisores["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count", text_auto=True), use_container_width=True)
            st.divider()
            st.write("📂 **Detalle por Supervisor:**")
            st.table(df_supervisores.groupby("ASIGNADO_A").size().reset_index(name="Pólizas"))

    with tab_tec:
        if not df_tecnicos.empty:
            col_a, col_b = st.columns(2)
            with col_a:
                st.info("🏠 Barrios por Técnico")
                # Mostrar cuántos barrios diferentes tiene cada técnico
                barrios_por_tec = df_tecnicos.groupby("ASIGNADO_A")[col_barrio].nunique().reset_index()
                st.plotly_chart(px.bar(barrios_por_tec, x="ASIGNADO_A", y=col_barrio, labels={col_barrio: "Cant. Barrios"}), use_container_width=True)
            with col_b:
                st.info("🥧 Composición por Subcategoría")
                st.plotly_chart(px.pie(df_tecnicos, names="SUBCATEGORIA", values="_deuda_num", hole=0.3), use_container_width=True)
        else:
            st.warning("No hay datos para operarios.")

else:
    st.info("👋 Sube el archivo para realizar la zonificación por barrios.")
