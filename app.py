import streamlit as st
import pandas as pd
import io

# Configuración de página
st.set_page_config(page_title="Sistema ITA - Reparto Seguro", layout="wide")
st.title("📊 Asignación con Intercambio Obligatorio")

# Unidades PH que NO deben intercambiar
mapeo_ph = {
    "ITA SUSPENSION BQ 15 PH": "HENRY CHAPMAN RUIZ",
    "ITA SUSPENSION BQ 31 PH": "SORELI FIGUEROA ALMARALES",
    "ITA SUSPENSION BQ 32 PH": "JENNIFER MARIA ALAMO DEL VALLE",
    "ITA SUSPENSION BQ 34 PH": "MIRANDIS MARIA MARENCO DOMINGUEZ",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 37 PH": "TATIANA ISABEL CASTRO GUZMAN"
}

# Nombres de columnas esperados (se limpiarán automáticamente)
COL_BARRIO = "BARRIO"
COL_CICLO = "CICLO_FACTURACION"
COL_TECNICO = "TECNICOS_INTEGRALES"
COL_UNIDAD = "UNIDAD_TRABAJO"
COL_DEUDA = "DEUDA_TOTAL"
COL_EDAD = "RANGO_EDAD"

@st.cache_data(ttl=3600)
def procesar_base_ligera(file):
    try:
        # Intentar cargar con motor rápido si está disponible
        df_raw = pd.read_excel(file)
    except Exception:
        df_raw = pd.read_excel(file, engine="openpyxl")
    
    # --- BLOQUE ANTIV-ERROR: LIMPIEZA DE COLUMNAS ---
    # Elimina espacios en blanco y convierte a MAYÚSCULAS para evitar el KeyError
    df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
    
    # Validar que la columna crítica existe tras la limpieza
    if COL_TECNICO not in df_raw.columns:
        st.error(f"❌ Error: No se encontró la columna '{COL_TECNICO}'. Columnas actuales: {list(df_raw.columns)}")
        st.stop()

    # Guardamos técnico original para validar intercambio
    df_raw["TEC_ORI"] = df_raw[COL_TECNICO].astype(str).str.strip()
    df_raw[COL_EDAD] = df_raw[COL_EDAD].astype(str).str.strip()
    
    # Limpieza de valores numéricos para la deuda
    df_raw["_VAL"] = pd.to_numeric(
        df_raw[COL_DEUDA].astype(str).str.replace(r"[^\d]", "", regex=True), 
        errors="coerce"
    ).fillna(0)
    
    return df_raw

archivo = st.file_uploader("Subir Seguimiento", type=["xlsx", "xlsb"])

if archivo:
    df = procesar_base_ligera(archivo)
    
    with st.sidebar:
        st.header("Filtros")
        ciclos = st.multiselect("Ciclos", df[COL_CICLO].unique(), default=df[COL_CICLO].unique())
        edades = st.multiselect("Edades", df[COL_EDAD].unique(), default=df[COL_EDAD].unique())
        nombres_ph = list(mapeo_ph.values())
        tecs_reparto = sorted([t for t in df["TEC_ORI"].unique() if t not in nombres_ph and t != "nan"])
        tecs_sel = st.multiselect("Técnicos a Intercambiar", tecs_reparto, default=tecs_reparto)

    if st.button("🚀 Iniciar Reparto"):
        # Filtrado por selecciones del usuario
        df_f = df[(df[COL_CICLO].isin(ciclos)) & (df[COL_EDAD].isin(edades))].copy()
        
        # 1. Separar PH (Los que tienen PH repiten su propia zona)
        df_ph = df_f[df_f[COL_UNIDAD].isin(mapeo_ph.keys())].copy()
        for und, tec in mapeo_ph.items():
            df_ph.loc[df_ph[COL_UNIDAD] == und, COL_TECNICO] = tec
        
        # 2. Reparto General con Intercambio (Los que NO son PH se intercambian)
        df_gen = df_f[~df_f[COL_UNIDAD].isin(mapeo_ph.keys())].copy()
        df_gen = df_gen.sort_values([COL_EDAD, COL_BARRIO], ascending=[False, True])
        
        final_rows = []
        asignados = set()
        
        # Bucle de asignación evitando el técnico original
        for tec in tecs_sel:
            pool = df_gen[(df_gen["TEC_ORI"] != tec) & (~df_gen.index.isin(asignados))].head(50)
            if not pool.empty:
                pool[COL_TECNICO] = tec
                final_rows.append(pool)
                asignados.update(pool.index)
        
        if final_rows or not df_ph.empty:
            df_resultado = pd.concat([df_ph] + final_rows)
            st.success(f"✅ Asignación lista: {len(df_resultado)} filas.")
            st.dataframe(df_resultado.head(100))
            
            # Preparar descarga en Excel
            towrite = io.BytesIO()
            df_resultado.to_excel(towrite, index=False, engine="openpyxl")
            st.download_button("📥 Descargar Excel", towrite.getvalue(), "Asignacion_Final.xlsx")
        else:
            st.warning("No se encontraron datos para los filtros seleccionados.")
