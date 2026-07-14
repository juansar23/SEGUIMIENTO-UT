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
    "ITA SUSPENSION BQ 27 PH": "LEONARDO ENRRIQUE RODRIGUEZ CERRANO",
    "ITA SUSPENSION BQ 42 PH": "MARIA TERESA SALAS OSPINO",
    "ITA SUSPENSION BQ 35 PH": "YONELIS DEL CARMEN MORELO MORELO",
    "ITA SUSPENSION BQ 36 PH": "YURANIS PATRICIA OSPINA CARCAMO",
    "ITA SUSPENSION BQ 33 PH": "TATIANA PATRICIA TAMARA PUELLO",
    "ITA SUSPENSION BQ 26 PH": "STIVEN ENRRIQUE DIAZ VELASQUEZ",
}

# Definición de columnas
COL_BARRIO, COL_CICLO = "BARRIO", "CICLO_FACTURACION"
COL_TECNICO, COL_UNIDAD = "TECNICOS_INTEGRALES", "UNIDAD_TRABAJO"
COL_DIRECCION, COL_EDAD = "DIRECCION", "RANGO_EDAD"
COL_SUBCAT = "SUBCATEGORIA"

def tipo_unidad(nombre):
    n = str(nombre).upper().strip()
    if n in [k.upper().strip() for k in mapeo_ph.keys()]:
        return "PH"
    elif "ITA GESTION" in n:
        return "GESTION"
    elif "ITA SUSPENSION" in n:
        return "SUSPENSION"
    return "OTRO"

@st.cache_data(ttl=3600)
def cargar_y_limpiar(file):
    df = pd.read_excel(file)
    df.columns = [str(c).strip().upper() for c in df.columns]
    df["TEC_ORI"] = df[COL_TECNICO].astype(str).str.strip()
    df["TIPO_UNIDAD"] = df[COL_UNIDAD].apply(tipo_unidad)
    # Guardamos un orden de origen fijo para poder desempatar SIEMPRE igual,
    # sin importar cuántas veces se filtre/reordene el dataframe después.
    df = df.reset_index(drop=True)
    df["ORDEN_ORIGEN"] = df.index
    return df

archivo = st.file_uploader("Sube el archivo de Seguimiento", type=["xlsx"])

if archivo:
    df = cargar_y_limpiar(archivo)

    tab_conf, tab_final = st.tabs(["⚙️ Configuración", "📋 Tabla Final"])

    with tab_conf:
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            excluir_ph = st.checkbox("🚫 EXCLUIR UNIDADES PH", value=False)
        with col_op2:
            modo_llenado = st.radio(
                "Si faltan pólizas para completar el cupo de cada técnico:",
                ["Solo usar barrios ajenos (puede dejar cupos vacíos)",
                 "Completar con sus propios barrios (priorizar cantidad)"]
            )

        c1, c2, c3 = st.columns(3)
        with c1:
            ciclos_sel = st.multiselect("Ciclos", sorted(df[COL_CICLO].unique().astype(str)), default=sorted(df[COL_CICLO].unique().astype(str)))
            subcat_sel = st.multiselect("Subcategoría", sorted(df[COL_SUBCAT].unique().astype(str)), default=sorted(df[COL_SUBCAT].unique().astype(str)))
        with c2:
            edades_disp = sorted([str(e) for e in df[COL_EDAD].unique() if str(e).lower() != "nan"])
            edades_sel = st.multiselect("Prioridad de Edad:", edades_disp, default=edades_disp)
        with c3:
            nombres_ph = list(mapeo_ph.values())

            # Separar técnicos por tipo
            tecs_gestion = sorted([
                str(t) for t in df["TEC_ORI"].unique()
                if str(t) not in nombres_ph and str(t).lower() != "nan"
                and not df[df["TEC_ORI"] == str(t)].empty
                and df[df["TEC_ORI"] == str(t)]["TIPO_UNIDAD"].iloc[0] == "GESTION"
            ])
            tecs_suspension = sorted([
                str(t) for t in df["TEC_ORI"].unique()
                if str(t) not in nombres_ph and str(t).lower() != "nan"
                and not df[df["TEC_ORI"] == str(t)].empty
                and df[df["TEC_ORI"] == str(t)]["TIPO_UNIDAD"].iloc[0] == "SUSPENSION"
            ])

            st.caption(f"👷 Técnicos Gestión ({len(tecs_gestion)}) — máx 25 pólizas c/u")
            tecnicos_gestion_sel = st.multiselect("Técnicos Gestión", tecs_gestion, default=tecs_gestion)
            st.caption(f"🔧 Técnicos Suspensión ({len(tecs_suspension)}) — máx 50 pólizas c/u")
            tecnicos_suspension_sel = st.multiselect("Técnicos Suspensión", tecs_suspension, default=tecs_suspension)

        ejecutar = st.button("🚀 Iniciar Distribución Geográfica")

    if ejecutar:
        # FIX 2: el orden en que Streamlit devuelve el multiselect depende del
        # orden en que el usuario clickeó/deseleccionó las opciones, no es alfabético.
        # Si no se fija ese orden, la asignación cambia cada vez que tocas un filtro
        # aunque el conjunto de técnicos seleccionados sea el mismo.
        tecnicos_gestion_sel = sorted(tecnicos_gestion_sel)
        tecnicos_suspension_sel = sorted(tecnicos_suspension_sel)

        df_base = df[
            (df[COL_CICLO].astype(str).isin(ciclos_sel)) &
            (df[COL_EDAD].astype(str).isin(edades_sel)) &
            (df[COL_SUBCAT].astype(str).isin(subcat_sel))
        ].copy()

        # FIX 1: sort_values usa quicksort por defecto, que NO es estable.
        # Con filas repetidas (mismo ciclo/barrio/dirección) el orden de los
        # empates puede variar entre corridas según cómo quede particionado
        # el array tras cada filtro -> por eso "se revolvían" los barrios y
        # direcciones. kind="mergesort" es estable: a igual contenido filtrado,
        # siempre el mismo orden. Como respaldo agregamos ORDEN_ORIGEN como
        # último criterio de desempate, así el resultado es 100% reproducible.
        df_base = df_base.sort_values(
            [COL_CICLO, COL_BARRIO, COL_DIRECCION, "ORDEN_ORIGEN"],
            kind="mergesort"
        ).reset_index(drop=True)

        indices_ocupados = set()
        lista_final = []

        # ── 1. ASIGNACIÓN PH (máx 50, solo su propia unidad) ──────────────────
        df_ph_final = pd.DataFrame()
        if not excluir_ph:
            mask_ph = df_base[COL_UNIDAD].isin(mapeo_ph.keys())
            df_ph_rows = df_base[mask_ph].copy()
            ph_lista = []
            for und, func in mapeo_ph.items():
                bloque = df_ph_rows[df_ph_rows[COL_UNIDAD] == und].head(50).copy()
                if not bloque.empty:
                    bloque[COL_TECNICO] = func
                    ph_lista.append(bloque)
                    indices_ocupados.update(bloque.index)
            if ph_lista:
                df_ph_final = pd.concat(ph_lista)

        # ── 2. ASIGNACIÓN GESTIÓN (máx 25, solo su propia unidad) ─────────────
        unidad_por_tec = df.drop_duplicates("TEC_ORI").set_index("TEC_ORI")[COL_UNIDAD].to_dict()

        for tec in tecnicos_gestion_sel:
            cupo = 25
            unidad_tec = unidad_por_tec.get(tec)
            if not unidad_tec:
                continue

            disponibles = df_base[
                (df_base[COL_UNIDAD] == unidad_tec) &
                (~df_base.index.isin(indices_ocupados))
            ]

            while cupo > 0 and not disponibles.empty:
                if "Solo usar barrios ajenos" in modo_llenado:
                    disponibles = disponibles[disponibles["TEC_ORI"] != tec]
                if disponibles.empty:
                    break

                barrio_actual = disponibles.iloc[0][COL_BARRIO]
                bloque = disponibles[disponibles[COL_BARRIO] == barrio_actual].head(cupo).copy()
                bloque[COL_TECNICO] = tec
                lista_final.append(bloque)
                indices_ocupados.update(bloque.index)
                cupo -= len(bloque)

                disponibles = df_base[
                    (df_base[COL_UNIDAD] == unidad_tec) &
                    (~df_base.index.isin(indices_ocupados))
                ]

        # ── 3. ASIGNACIÓN SUSPENSIÓN (máx 50: sus unidades + restante gestión) ─
        unidades_suspension = [u for u in df_base[COL_UNIDAD].unique() if tipo_unidad(u) == "SUSPENSION"]
        unidades_gestion = [u for u in df_base[COL_UNIDAD].unique() if tipo_unidad(u) == "GESTION"]

        df_susp_pool = df_base[
            df_base[COL_UNIDAD].isin(unidades_suspension + unidades_gestion)
        ]

        for tec in tecnicos_suspension_sel:
            cupo = 50

            while cupo > 0:
                disponibles = df_susp_pool[~df_susp_pool.index.isin(indices_ocupados)]
                if disponibles.empty:
                    break

                if "Solo usar barrios ajenos" in modo_llenado:
                    disponibles = disponibles[disponibles["TEC_ORI"] != tec]
                if disponibles.empty:
                    break

                barrio_actual = disponibles.iloc[0][COL_BARRIO]
                bloque = disponibles[disponibles[COL_BARRIO] == barrio_actual].head(cupo).copy()
                bloque[COL_TECNICO] = tec
                lista_final.append(bloque)
                indices_ocupados.update(bloque.index)
                cupo -= len(bloque)

        with tab_final:
            if lista_final or not df_ph_final.empty:
                partes = ([df_ph_final] if not df_ph_final.empty else []) + lista_final
                df_res = pd.concat(partes, ignore_index=True)
                st.success(f"Asignación terminada: {len(df_res)} pólizas.")
                st.dataframe(df_res.drop(columns=["TEC_ORI", "TIPO_UNIDAD", "ORDEN_ORIGEN"]), use_container_width=True)

                output = io.BytesIO()
                df_res.drop(columns=["TEC_ORI", "TIPO_UNIDAD", "ORDEN_ORIGEN"]).to_excel(output, index=False)
                st.download_button("📥 Descargar Reporte", output.getvalue(), "Reparto_Geografico.xlsx")
            else:
                st.warning("No se encontraron registros con los filtros actuales.")
