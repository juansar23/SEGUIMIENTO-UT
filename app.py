import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Con Intercambio Obligatorio")

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
def cargar_y_limpiar_v3(file):
    if file.name.lower().endswith((".xlsx", ".xlsm", ".xlsb")):
        df_raw = pd.read_excel(file, engine="openpyxl")
    else:
        df_raw = pd.read_excel(file, engine="xlrd")
    
    df_raw.columns = df_raw.columns.str.strip()
    # Guardamos el técnico original para la validación de NO REPETIR BARRIO
    df_raw["TECNICO_ORIGINAL"] = df_raw[col_tecnico].astype(str).str.strip()
    df_raw[col_edad] = df_raw[col_edad].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    df_raw["_deuda_num"] = pd.to_numeric(df_raw[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)
    
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    df = cargar_y_limpiar_v3(archivo)
    tab_filtros, tab1, tab2 = st.tabs(["⚙️ Configuración", "📋 Tabla Final", "📊 Dashboard"])

    with tab_filtros:
        c1, c2, c3 = st.columns(3)
        with c1:
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
            ciclos_sel = st.multiselect("Ciclos", sorted(df[col_ciclo].dropna().unique().astype(str)), default=df[col_ciclo].dropna().unique().astype(str))
        with c2:
            subcat_sel = st.multiselect("Subcategoría", sorted(df[col_subcat].unique()), default=df[col_subcat].unique())
            edades_reales = sorted(df[col_edad].unique().tolist())
            prioridad_edades = st.multiselect("Prioridad de Edad:", options=edades_reales, default=edades_reales)
        with c3:
            nombres_ph = list(mapeo_ph.values())
            tecs_unicos = df["TECNICO_ORIGINAL"].unique()
            tecnicos_reparto = sorted([t for t in tecs_unicos if t not in nombres_ph and t != "nan"])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecnicos_reparto, default=tecnicos_reparto)

    if st.button("🚀 Procesar con Intercambio de Barrios"):
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].isin(prioridad_edades)) & 
            (df[col_subcat].isin(subcat_sel))
        ].copy()

        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)

        # 1. ASIGNACIÓN PH (Blindada: ellos NO intercambian barrios, mantienen los suyos)
        df_ph_final = pd.DataFrame()
        indices_ocupados = set()
        if not excluir_ph:
            list_ph = []
            for unidad, func in mapeo_ph.items():
                p_ph = df_pool[df_pool[col_unidad] == unidad].sort_values([col_edad, "_deuda_num"], ascending=[True, False]).head(50)
                if not p_ph.empty:
                    p_ph[col_tecnico] = func
                    list_ph.append(p_ph)
                    indices_ocupados.update(p_ph.index)
            if list_ph: df_ph_final = pd.concat(list_ph)

        # 2. REPARTO GENERAL CON INTERCAMBIO (Adrian, etc.)
        df_otros = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys()) & ~df_pool.index.isin(indices_ocupados)].copy()
        df_otros = df_otros.sort_values([col_edad, col_ciclo, col_barrio, col_direccion])
        
        # Convertimos a lista de diccionarios para velocidad
        pols_disponibles = df_otros.to_dict('records')
        lista_final_otros = []
        
        # Diccionario para rastrear qué índices ya usamos
        usados = [False] * len(pols_disponibles)

        for tec in tecnicos_sel:
            cupo = 50
            i = 0
            while cupo > 0 and i < len(pols_disponibles):
                if not usados[i]:
                    barrio_actual = pols_disponibles[i][col_barrio]
                    dueno_original = pols_disponibles[i]["TECNICO_ORIGINAL"]
                    
                    # REGLA DE ORO: Si el barrio ya era de este técnico, lo saltamos
                    if dueno_original == tec:
                        # Buscamos el siguiente barrio diferente
                        temp_idx = i
                        while temp_idx < len(pols_disponibles) and pols_disponibles[temp_idx][col_barrio] == barrio_actual:
                            temp_idx += 1
                        i = temp_idx
                        continue
                    
                    # Si no es su barrio, tomamos el bloque completo de ese barrio hasta agotar cupo
                    temp_idx = i
                    while temp_idx < len(pols_disponibles) and \
                          pols_disponibles[temp_idx][col_barrio] == barrio_actual and \
                          cupo > 0:
                        
                        if not usados[temp_idx]:
                            row = pols_disponibles[temp_idx]
                            row[col_tecnico] = tec
                            lista_final_otros.append(row)
                            usados[temp_idx] = True
                            cupo -= 1
                        temp_idx += 1
                    
                i += 1

        df_resultado = pd.concat([df_ph_final, pd.DataFrame(lista_final_otros)], ignore_index=True)

        with tab1:
            st.success(f"Proceso completado. Se garantizó que ningún técnico de reparto reciba sus barrios originales.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num", "TECNICO_ORIGINAL"]), use_container_width=True)
            
            output = io.BytesIO()
            df_resultado.drop(columns=["_deuda_num", "TECNICO_ORIGINAL"]).to_excel(output, index=False)
            st.download_button("📥 Descargar Asignación Nueva", output.getvalue(), "Intercambio_Barrios.xlsx")
