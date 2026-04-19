import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración inicial
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Intercambio Seguro")

# Mapeo de Unidades PH (Blindadas)
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Columnas estándar
col_barrio, col_ciclo, col_direccion = "BARRIO", "CICLO_FACTURACION", "DIRECCION"
col_tecnico, col_unidad, col_deuda = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO", "DEUDA_TOTAL"
col_edad, col_subcat = "RANGO_EDAD", "SUBCATEGORIA"

@st.cache_data(show_spinner="Cargando y normalizando datos...")
def cargar_base_optimizada(file):
    # Lectura eficiente
    df_raw = pd.read_excel(file)
    df_raw.columns = df_raw.columns.str.strip()
    
    # Normalización para evitar errores de filtros
    df_raw[col_edad] = df_raw[col_edad].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    df_raw["TECNICO_ORIGINAL"] = df_raw[col_tecnico].astype(str).str.strip()
    df_raw["_deuda_num"] = pd.to_numeric(df_raw[col_deuda].astype(str).str.replace(r"[\$,.]", "", regex=True), errors="coerce").fillna(0)
    
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

if archivo:
    df = cargar_base_optimizada(archivo)
    
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
            tecnicos_reparto = sorted([t for t in df["TECNICO_ORIGINAL"].unique() if t not in nombres_ph and t != "nan"])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecnicos_reparto, default=tecnicos_reparto)

    if st.button("🚀 Procesar Asignación con Intercambio"):
        # 1. Filtrado inicial rápido
        df_pool = df[
            (df[col_ciclo].astype(str).isin(ciclos_sel)) & 
            (df[col_edad].isin(prioridad_edades)) & 
            (df[col_subcat].isin(subcat_sel))
        ].copy()

        df_pool[col_edad] = pd.Categorical(df_pool[col_edad], categories=prioridad_edades, ordered=True)

        # 2. Asignación PH (Unidades que no intercambian)
        df_ph_final = pd.DataFrame()
        indices_ph = set()
        if not excluir_ph:
            list_ph = []
            for unidad, funcionario in mapeo_ph.items():
                p_ph = df_pool[df_pool[col_unidad] == unidad].sort_values([col_edad, "_deuda_num"], ascending=[True, False]).head(50)
                if not p_ph.empty:
                    p_ph[col_tecnico] = funcionario
                    list_ph.append(p_ph)
                    indices_ph.update(p_ph.index)
            if list_ph: df_ph_final = pd.concat(list_ph)

        # 3. Reparto General con Intercambio Obligatorio
        df_otros = df_pool[~df_pool[col_unidad].isin(mapeo_ph.keys()) & ~df_pool.index.isin(indices_ph)].copy()
        df_otros = df_otros.sort_values([col_edad, col_ciclo, col_barrio, col_direccion])
        
        # Trabajamos con listas para máxima velocidad
        registros = df_otros.to_dict('records')
        indices_disponibles = list(range(len(registros)))
        lista_final_otros = []

        for tec in tecnicos_sel:
            cupo = 50
            # Buscamos primero barrios que NO sean del técnico
            i = 0
            while i < len(indices_disponibles) and cupo > 0:
                idx = indices_disponibles[i]
                reg = registros[idx]
                
                # REGLA: ¿Es su barrio original?
                if reg["TECNICO_ORIGINAL"] != tec:
                    barrio_actual = reg[col_barrio]
                    
                    # Tomar todo el bloque de ese barrio que no sea suyo
                    temp_idx = i
                    while temp_idx < len(indices_disponibles) and cupo > 0:
                        curr_idx = indices_disponibles[temp_idx]
                        if registros[curr_idx][col_barrio] == barrio_actual:
                            # Solo asignamos si el dueño original no es el técnico actual
                            if registros[curr_idx]["TECNICO_ORIGINAL"] != tec:
                                registros[curr_idx][col_tecnico] = tec
                                lista_final_otros.append(registros[curr_idx])
                                indices_disponibles.pop(temp_idx)
                                cupo -= 1
                            else:
                                temp_idx += 1
                        else:
                            break
                else:
                    i += 1
            
            # Plan B: Si aún le queda cupo y ya no hay barrios de otros, toma lo que quede
            if cupo > 0 and len(indices_disponibles) > 0:
                for _ in range(cupo):
                    if indices_disponibles:
                        idx = indices_disponibles.pop(0)
                        registros[idx][col_tecnico] = tec
                        lista_final_otros.append(registros[idx])
                        cupo -= 1

        df_resultado = pd.concat([df_ph_final, pd.DataFrame(lista_final_otros)], ignore_index=True)

        with tab1:
            st.success("✅ Proceso completado exitosamente.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num", "TECNICO_ORIGINAL"]), use_container_width=True)
            
            output = io.BytesIO()
            df_resultado.drop(columns=["_deuda_num", "TECNICO_ORIGINAL"]).to_excel(output, index=False)
            st.download_button("📥 Descargar Resultados", output.getvalue(), "Asignacion_Segura.xlsx")
