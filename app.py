import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Optimizado")

mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Columnas
col_barrio, col_ciclo, col_direccion = "BARRIO", "CICLO_FACTURACION", "DIRECCION"
col_tecnico, col_unidad, col_deuda = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO", "DEUDA_TOTAL"
col_edad, col_subcat = "RANGO_EDAD", "SUBCATEGORIA"

@st.cache_data(show_spinner="Limpiando base de datos...")
def cargar_y_limpiar_v2(file):
    # Cargar según extensión
    if file.name.lower().endswith((".xlsx", ".xlsm", ".xlsb")):
        df_raw = pd.read_excel(file, engine="openpyxl")
    else:
        df_raw = pd.read_excel(file, engine="xlrd")
    
    df_raw.columns = df_raw.columns.str.strip()
    
    # --- LIMPIEZA AGRESIVA DE EDADES ---
    # 1. Convertir a string y quitar espacios extremos
    # 2. Reemplazar múltiples espacios internos por uno solo
    df_raw[col_edad] = df_raw[col_edad].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Limpieza de deuda
    df_raw["_deuda_num"] = pd.to_numeric(df_raw[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)
    
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    # Si subes un archivo nuevo, forzamos la limpieza
    df = cargar_y_limpiar_v2(archivo)

    tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

    with tab_filtros:
        c1, c2, c3 = st.columns(3)
        with c1:
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
            ciclos_sel = st.multiselect("Ciclos", sorted(df[col_ciclo].dropna().unique().astype(str)), 
                                        default=df[col_ciclo].dropna().unique().astype(str))
        with c2:
            subcat_sel = st.multiselect("Subcategoría", sorted(df[col_subcat].unique()), 
                                        default=df[col_subcat].unique())
            
            # DINÁMICO: Obtenemos lo que REALMENTE hay en el Excel después de limpiar
            edades_reales = sorted(df[col_edad].unique().tolist())
            prioridad_edades = st.multiselect("Prioridad de Edad:", 
                                              options=edades_reales, 
                                              default=edades_reales)
        with c3:
            nombres_ph = list(mapeo_ph.values())
            tecnicos_reparto = sorted([t for t in df[col_tecnico].dropna().unique() if str(t) not in nombres_ph])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecnicos_reparto, default=tecnicos_reparto)

    if st.button("🚀 Procesar Asignación"):
        # Filtrado
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].isin(prioridad_edades)) & 
            (df[col_subcat].isin(subcat_sel))
        ].copy()

        # Ordenar por la prioridad que el usuario eligió en el multiselect
        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)

        # 1. Asignación PH
        df_ph_final = pd.DataFrame()
        indices_ph = set()
        if not excluir_ph:
            list_ph = []
            for unidad, func in mapeo_ph.items():
                p_ph = df_pool[df_pool[col_unidad] == unidad].sort_values([col_edad, "_deuda_num"], ascending=[True, False]).head(50)
                if not p_ph.empty:
                    p_ph[col_tecnico] = func
                    list_ph.append(p_ph)
                    indices_ph.update(p_ph.index)
            if list_ph: df_ph_final = pd.concat(list_ph)

        # 2. Reparto General (Optimizado)
        df_otros = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys()) & ~df_pool.index.isin(indices_ph)].copy()
        df_otros = df_otros.sort_values([col_edad, col_ciclo, col_barrio, col_direccion])
        
        pols_disponibles = df_otros.to_dict('records')
        lista_final_otros = []
        idx_pols = 0
        total_pols = len(pols_disponibles)

        for tec in tecnicos_sel:
            cupo = 50
            while cupo > 0 and idx_pols < total_pols:
                barrio_actual = pols_disponibles[idx_pols][col_barrio]
                while idx_pols < total_pols and pols_disponibles[idx_pols][col_barrio] == barrio_actual and cupo > 0:
                    row = pols_disponibles[idx_pols]
                    row[col_tecnico] = tec
                    lista_final_otros.append(row)
                    idx_pols += 1
                    cupo -= 1

        df_final_reparto = pd.DataFrame(lista_final_otros)
        df_resultado = pd.concat([df_ph_final, df_final_reparto], ignore_index=True)

        with tab1:
            st.success(f"Se asignaron {len(df_ph_final)} pólizas PH y {len(df_final_reparto)} de reparto general.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            df_resultado.drop(columns=["_deuda_num"]).to_excel(output, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), "Asignacion_Final.xlsx")
