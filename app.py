import streamlit as st
import pandas as pd
import io
import plotly.express as px
import plotly.graph_objects as go

# Configuración de página
st.set_page_config(page_title="Gestión UT - Sistema ITA", layout="wide")

# Estilo CSS
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

st.title("🚀 Sistema ITA - Gestión PH (Continuidad) y Operativa (Rotación)")

SUPERVISORES_NOMINA = [
    "FAVIO ERNESTO VASQUEZ ROMERO", "DEGUIN ZOCRATE DEGUIN ZOCRATE",
    "YESID RAFAEL REALES MORENO", "ABILIO SEGUNDO ARAUJO ARIÑO",
    "JAVIER DAVID GOMEZ BARRIOS"
]

archivo = st.file_uploader("📂 Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()
    col_barrio = "BARRIO" if "BARRIO" in df.columns else "NOMBRE_BARRIO"
    
    # Limpieza de Deuda
    df["_deuda_num"] = (
        df["DEUDA_TOTAL"].astype(str)
        .str.replace("$", "", regex=False).str.replace(",", "", regex=False)
        .str.replace(".", "", regex=False).str.strip()
    )
    df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

    # Sidebar
    st.sidebar.header("🎯 Panel de Control")
    opciones_edad = sorted(df["RANGO_EDAD"].dropna().astype(str).unique())
    opciones_sub = sorted(df["SUBCATEGORIA"].dropna().astype(str).unique())
    tecs_disponibles = sorted(df["TECNICOS_INTEGRALES"].dropna().astype(str).unique())

    rangos_sel = st.sidebar.multiselect("Rango Edad", opciones_edad, default=opciones_edad)
    sub_sel = st.sidebar.multiselect("Subcategoría", opciones_sub, default=opciones_sub)
    deuda_minima = st.sidebar.number_input("Deuda mínima ($)", value=100000)
    sups_final = st.sidebar.multiselect("Supervisores", SUPERVISORES_NOMINA, default=SUPERVISORES_NOMINA)
    tecs_final = st.sidebar.multiselect("Técnicos Activos", tecs_disponibles, default=tecs_disponibles)

    # 1. Base Filtrada
    df_base = df[
        (df["RANGO_EDAD"].astype(str).isin(rangos_sel)) &
        (df["SUBCATEGORIA"].astype(str).isin(sub_sel)) &
        (df["_deuda_num"] >= deuda_minima)
    ].copy()

    # 2. Asignación Supervisores
    df_base = df_base.sort_values("_deuda_num", ascending=False)
    df_sup = df_base.head(len(sups_final) * 8).copy()
    barrios_bloqueados = set()
    if not df_sup.empty:
        nombres_sups = []
        for s in sups_final: nombres_sups.extend([s] * 8)
        df_sup["ASIGNADO_A"] = nombres_sups[:len(df_sup)]
        barrios_bloqueados = set(df_sup[col_barrio].unique())

    # 3. Preparación de Operarios
    df_restante = df_base.drop(df_sup.index) if not df_sup.empty else df_base
    df_disp = df_restante[~df_restante[col_barrio].isin(barrios_bloqueados)].copy()
    
    tecs_ph = [t for t in tecs_final if "PH" in str(t).upper()]
    tecs_std = [t for t in tecs_final if "PH" not in str(t).upper()]
    
    conteo_polizas = {t: 0 for t in tecs_final}
    asignaciones_finales = []

    # --- MOTOR DE ASIGNACIÓN (CORREGIDO: PH REPITE, STD ROTAN) ---
    barrios_grupos = df_disp.groupby(col_barrio)
    barrios_ordenados = sorted(barrios_grupos, key=lambda x: x[1]["_deuda_num"].sum(), reverse=True)

    for nombre_barrio, datos_barrio in barrios_ordenados:
        for tipo_clase in ["PH", "STD"]:
            if tipo_clase == "PH":
                pols_barrio = datos_barrio[datos_barrio["TECNICOS_INTEGRALES"].str.contains("PH", na=False, case=False)]
                candidatos_grupo = tecs_ph
            else:
                pols_barrio = datos_barrio[~datos_barrio["TECNICOS_INTEGRALES"].str.contains("PH", na=False, case=False)]
                candidatos_grupo = tecs_std
            
            if pols_barrio.empty: continue

            for idx, row in pols_barrio.iterrows():
                # REGLAS DE ASIGNACIÓN
                if tipo_clase == "PH":
                    # PH: PUEDE REPETIR su propia póliza (Continuidad)
                    validos = [t for t in candidatos_grupo if conteo_polizas[t] < 50]
                else:
                    # STD (Operativa): PROHIBIDO REPETIR (Rotación/Transparencia)
                    validos = [t for t in candidatos_grupo if conteo_polizas[t] < 50 and t != row["TECNICOS_INTEGRALES"]]
                
                if validos:
                    # 1. Si es PH, intentar primero asignar al que ya tiene la póliza
                    original_ph = [t for t in validos if t == row["TECNICOS_INTEGRALES"]]
                    
                    # 2. Intentar mantener el mismo técnico en el mismo barrio
                    ya_en_barrio = [t for t in validos if any(a['ASIGNADO_A'] == t and a[col_barrio] == nombre_barrio for a in asignaciones_finales)]
                    
                    if tipo_clase == "PH" and original_ph:
                        elegido = original_ph[0]
                    elif ya_en_barrio:
                        elegido = ya_en_barrio[0]
                    else:
                        elegido = min(validos, key=lambda x: conteo_polizas[x])
                    
                    nueva = row.copy()
                    nueva["ASIGNADO_A"] = elegido
                    asignaciones_finales.append(nueva)
                    conteo_polizas[elegido] += 1

    df_tec = pd.DataFrame(asignaciones_finales)

    # ================================
    # DASHBOARD
    # ================================
    tab_res, tab_sup, tab_tec = st.tabs(["📑 Reporte General", "👨‍💼 Supervisores", "👥 Operarios"])

    def kpi_grafico(titulo, valor, es_moneda=True):
        fig = go.Figure(go.Indicator(
            mode="number", value=valor,
            number={'prefix': "$ " if es_moneda else "", 'valueformat': ",.0f"},
            title={"text": titulo, 'font': {'size': 18}}
        ))
        fig.update_layout(height=150, margin=dict(l=10, r=10, t=30, b=10))
        return fig

    with tab_res:
        df_final = pd.concat([df_sup, df_tec], ignore_index=True)
        st.dataframe(df_final.drop(columns=["_deuda_num"]), use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Plan_Final")
        st.download_button("📥 Descargar Plan de Trabajo", data=output.getvalue(), file_name="plan_ita_corregido.xlsx")

    with tab_sup:
        if not df_sup.empty:
            c1, c2 = st.columns(2)
            c1.plotly_chart(kpi_grafico("Deuda Supervisión", df_sup["_deuda_num"].sum()), use_container_width=True)
            c2.plotly_chart(kpi_grafico("Pólizas Supervisión", len(df_sup), False), use_container_width=True)
            st.write("🏆 **Ranking de Supervisores**")
            st.table(df_sup.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).reset_index().style.format({"_deuda_num": "$ {:,.0f}"}))

    with tab_tec:
        if not df_tec.empty:
            c3, c4 = st.columns(2)
            c3.plotly_chart(kpi_grafico("Deuda Operarios", df_tec["_deuda_num"].sum()), use_container_width=True)
            c4.plotly_chart(kpi_grafico("Pólizas Operarios", len(df_tec), False), use_container_width=True)
            st.write("🏆 **Top 10 Operarios (Mayor Deuda)**")
            st.table(df_tec.groupby("ASIGNADO_A")["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index().style.format({"_deuda_num": "$ {:,.0f}"}))
            
            colA, colB = st.columns(2)
            with colA:
                st.info("📊 Cantidad por Rango Edad")
                st.plotly_chart(px.bar(df_tec["RANGO_EDAD"].astype(str).value_counts().reset_index(), x="RANGO_EDAD", y="count"), use_container_width=True)
            with colB:
                st.info("🥧 Composición Subcategoría")
                st.plotly_chart(px.pie(df_tec, names="SUBCATEGORIA", values="_deuda_num", hole=0.4), use_container_width=True)

else:
    st.info("👋 Sube el archivo Excel para procesar con las reglas PH corregidas.")
