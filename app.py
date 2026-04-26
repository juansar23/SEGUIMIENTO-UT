import streamlit as st
import pandas as pd
import io

# Configuración inicial
st.set_page_config(page_title="Dashboard Ejecutivo - Agrupación Geográfica", layout="wide")
st.title("📊 Distribución Geográfica Inteligente")

# Mapeo PH (Unidades Blindadas)
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN",
    "ITA SUSPENSION BQ 26": "STIVEN ENRRIQUE DIAZ VELASQUEZ",


}

# Definición de columnas con normalización
COL_BARRIO, COL_CICLO = "BARRIO", "CICLO_FACTURACION"
COL_TECNICO, COL_UNIDAD = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO"
COL_DIRECCION, COL_EDAD = "DIRECCION", "RANGO_EDAD"
COL_SUBCAT = "SUBCATEGORIA"

@st.cache_data(ttl=3600)
def cargar_y_limpiar(file):
    df = pd.read_excel(file)
    # Limpieza de encabezados para evitar el KeyError visto en logs
    df.columns = [str(c).strip().upper() for c in df.columns]
    # Columna auxiliar para validar el intercambio obligatorio
    df["TEC_ORI"] = df[COL_TECNICO].astype(str).str.strip()
    return df

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xlsx"])

if archivo:
    df = cargar_y_limpiar(archivo)
    
    tab_conf, tab_final = st.tabs(["⚙️ Configuración", "📋 Tabla Final"])

    with tab_conf:
        # 1. OPCIONES DE EXCLUSIÓN Y CONTINGENCIA
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
        with col_op2:
            modo_llenado = st.radio(
                "Si faltan pólizas para completar los 50 de cada técnico:",
                ["Solo usar barrios ajenos (puede dejar cupos vacíos)", 
                 "Completar con sus propios barrios (priorizar cantidad)"]
            )

        # 2. FILTROS
        c1, c2, c3 = st.columns(3)
        with c1:
            ciclos_sel = st.multiselect("Ciclos", sorted(df[COL_CICLO].unique().astype(str)), default=df[COL_CICLO].unique().astype(str))
            subcat_sel = st.multiselect("Subcategoría", sorted(df[COL_SUBCAT].unique().astype(str)), default=df[COL_SUBCAT].unique().astype(str))
        with c2:
            edades_disp = sorted([str(e) for e in df[COL_EDAD].unique() if str(e).lower() != "nan"])
            edades_sel = st.multiselect("Prioridad de Edad:", edades_disp, default=edades_disp)
        with c3:
            nombres_ph = list(mapeo_ph.values())
            tecs_reparto = sorted([str(t) for t in df["TEC_ORI"].unique() if str(t) not in nombres_ph and str(t).lower() != "nan"])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecs_reparto, default=tecs_reparto)

        ejecutar = st.button("🚀 Iniciar Distribución Geográfica")

    if ejecutar:
        # Filtrado por criterios del usuario
        df_base = df[
            (df[COL_CICLO].astype(str).isin(ciclos_sel)) & 
            (df[COL_EDAD].astype(str).isin(edades_sel)) &
            (df[COL_SUBCAT].astype(str).isin(subcat_sel))
        ].copy()

        # ORDENAMIENTO PRIORITARIO: Ciclo -> Barrio -> Dirección
        df_base = df_base.sort_values([COL_CICLO, COL_BARRIO, COL_DIRECCION])

        # A. Separar PH
        df_ph_final = pd.DataFrame()
        indices_ocupados = set()
        if not excluir_ph:
            mask_ph = df_base[COL_UNIDAD].isin(mapeo_ph.keys())
            df_ph_final = df_base[mask_ph].copy()
            for und, func in mapeo_ph.items():
                df_ph_final.loc[df_ph_final[COL_UNIDAD] == und, COL_TECNICO] = func
            indices_ocupados.update(df_ph_final.index)

        # B. Reparto General por Bloques Geográficos
        df_pool = df_base[~df_base.index.isin(indices_ocupados)].copy()
        lista_final = []
        
        for tec in tecnicos_sel:
            cupo = 50
            while cupo > 0:
                # Filtrar lo que aún no ha sido asignado
                disponibles = df_pool[~df_pool.index.isin(indices_ocupados)]
                
                if disponibles.empty:
                    break
                
                # Aplicar restricción de "No repetir su propio barrio" según configuración
                if "Solo usar barrios ajenos" in modo_llenado:
                    disponibles = disponibles[disponibles["TEC_ORI"] != tec]
                
                if disponibles.empty:
                    break
                
                # Tomar el primer barrio disponible en la cola (el más cercano por el sort previo)
                barrio_actual = disponibles.iloc[0][COL_BARRIO]
                bloque_barrio = disponibles[disponibles[COL_BARRIO] == barrio_actual]
                
                # Definir cuántas pólizas de este barrio toma el técnico
                toma = min(len(bloque_barrio), cupo)
                seleccion = bloque_barrio.head(toma).copy()
                
                seleccion[COL_TECNICO] = tec
                lista_final.append(seleccion)
                indices_ocupados.update(seleccion.index)
                cupo -= toma

        with tab_final:
            if lista_final or not df_ph_final.empty:
                df_res = pd.concat([df_ph_final] + lista_final, ignore_index=True)
                st.success(f"Asignación Geográfica terminada: {len(df_res)} pólizas.")
                st.dataframe(df_res.drop(columns=["TEC_ORI"]), use_container_width=True)
                
                output = io.BytesIO()
                df_res.drop(columns=["TEC_ORI"]).to_excel(output, index=False)
                st.download_button("📥 Descargar Reporte", output.getvalue(), "Reparto_Geografico.xlsx")
            else:
                st.warning("No se encontraron registros con los filtros actuales.")
