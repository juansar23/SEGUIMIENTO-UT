import streamlit as st
import pandas as pd
import io

# Configuración
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")
st.title("📊 Dashboard Ejecutivo - Asignación con Intercambio")

# Mapeo de Unidades PH
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Nombres de columnas esperados
COL_BARRIO, COL_CICLO = "BARRIO", "CICLO_FACTURACION"
COL_TECNICO, COL_UNIDAD = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO"
COL_DEUDA, COL_EDAD = "DEUDA_TOTAL", "RANGO_EDAD"

@st.cache_data(ttl=3600)
def cargar_base_segura(file):
    try:
        df_raw = pd.read_excel(file)
    except:
        df_raw = pd.read_excel(file, engine="openpyxl")
    
    # Limpieza agresiva de columnas para evitar KeyError
    df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
    
    # Crear columna auxiliar de origen
    if COL_TECNICO in df_raw.columns:
        df_raw["TEC_ORI"] = df_raw[COL_TECNICO].astype(str).str.strip()
    
    return df_raw

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xlsx", "xlsb"])

if archivo:
    df = cargar_base_segura(archivo)
    
    # Verificación de seguridad
    if COL_TECNICO not in df.columns:
        st.error(f"No se encontró la columna '{COL_TECNICO}'. Verifica tu Excel.")
        st.stop()

    tab_filtros, tab_resultado = st.tabs(["⚙️ Configuración", "📋 Tabla Final"])

    with tab_filtros:
        # BOTÓN SOLICITADO: EXCLUIR PH
        excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            ciclos_sel = st.multiselect("Ciclos", sorted(df[COL_CICLO].unique().astype(str)), default=df[COL_CICLO].unique().astype(str))
        with c2:
            edades_disp = sorted(df[COL_EDAD].astype(str).unique())
            prioridad_edades = st.multiselect("Prioridad de Edad:", edades_disp, default=edades_disp)
        with c3:
            nombres_ph = list(mapeo_ph.values())
            tecs_reparto = sorted([t for t in df["TEC_ORI"].unique() if t not in nombres_ph and t != "nan"])
            tecnicos_sel = st.multiselect("Técnicos Reparto", tecs_reparto, default=tecs_reparto)
        
        procesar = st.button("🚀 Procesar Asignación")

    if procesar:
        # Filtrado
        df_f = df[(df[COL_CICLO].astype(str).isin(ciclos_sel)) & (df[COL_EDAD].astype(str).isin(prioridad_edades))].copy()
        
        # 1. Manejo de PH
        df_ph_final = pd.DataFrame()
        if not excluir_ph:
            df_ph_final = df_f[df_f[COL_UNIDAD].isin(mapeo_ph.keys())].copy()
            for und, tec in mapeo_ph.items():
                df_ph_final.loc[df_ph_final[COL_UNIDAD] == und, COL_TECNICO] = tec
        
        # 2. Reparto General con Intercambio
        df_gen = df_f[~df_f[COL_UNIDAD].isin(mapeo_ph.keys())].copy()
        df_gen = df_gen.sort_values([COL_EDAD, COL_BARRIO], ascending=[False, True])
        
        final_reparto = []
        asignados = set()
        
        for tec in tecnicos_sel:
            # Selecciona 50 que NO sean del mismo técnico original
            pool = df_gen[(df_gen["TEC_ORI"] != tec) & (~df_gen.index.isin(asignados))].head(50)
            if not pool.empty:
                pool[COL_TECNICO] = tec
                final_reparto.append(pool)
                asignados.update(pool.index)
        
        df_resultado = pd.concat([df_ph_final] + final_reparto) if (not df_ph_final.empty or final_reparto) else pd.DataFrame()

        with tab_resultado:
            if not df_resultado.empty:
                st.success(f"Asignación completada: {len(df_resultado)} registros.")
                st.dataframe(df_resultado.drop(columns=["TEC_ORI"]), use_container_width=True)
                
                output = io.BytesIO()
                df_resultado.drop(columns=["TEC_ORI"]).to_excel(output, index=False, engine="openpyxl")
                st.download_button("📥 Descargar Excel", output.getvalue(), "Asignacion_Final.xlsx")
            else:
                st.warning("No hay datos que coincidan con los filtros.")
