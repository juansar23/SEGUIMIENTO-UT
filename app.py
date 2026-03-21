import streamlit as st
import pandas as pd
import io
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización Logística")

# --- SIDEBAR: CONFIGURACIÓN Y FILTROS ---
st.sidebar.header("⚙️ Configuración y Filtros")

# Soporte para archivos .xls antiguos y .xlsx modernos
archivo = st.sidebar.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Nombres de columnas según tus archivos
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"
col_edad = "RANGO_EDAD"
col_subcat = "SUBCATEGORIA"

if archivo:
    try:
        # LECTURA DE DATOS
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()

        # Limpieza de Deuda
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # FILTROS
        ciclos_disp = sorted(df[col_ciclo].unique())
        ciclos_sel = st.sidebar.multiselect("Ciclo Facturación", ciclos_disp, default=ciclos_disp)
        
        todos_tecnicos = sorted(df[col_tecnico].astype(str).unique())
        modo_exclusion = st.sidebar.checkbox("Seleccionar todos excepto")
        if modo_exclusion:
            excluir = st.sidebar.multiselect("Excluir técnicos:", todos_tecnicos)
            tecnicos_final = [t for t in todos_tecnicos if t not in excluir]
        else:
            tecnicos_final = st.sidebar.multiselect("Incluir técnicos:", todos_tecnicos, default=todos_tecnicos)

        # Aplicar filtros base
        df_base = df[
            (df[col_ciclo].isin(ciclos_sel)) & 
            (df[col_tecnico].isin(tecnicos_final))
        ].copy()

        # --- LÓGICA DE ASIGNACIÓN CONCENTRADA (EVITAR DIVIDIR BARRIOS) ---
        unidades_ph = ["ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", "ITA SUSPENSION BQ 32 PH", 
                       "ITA SUSPENSION BQ 34 PH", "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", "ITA SUSPENSION BQ 37 PH"]

        # 1. PH mantienen su lógica de mayor deuda
        df_ph = df_base[df_base[col_tecnico].isin(unidades_ph)].copy()
        df_ph_final = df_ph.sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        # 2. Otros: Priorizar que un barrio se quede con un solo técnico
        df_otros = df_base[~df_base[col_tecnico].isin(unidades_ph)].copy()
        lista_rutas = []
        
        # Pólizas ya asignadas para no repetir
        pólizas_asignadas_ids = set()

        for tec in tecnicos_final:
            if tec in unidades_ph: continue
            
            grupo_tec = df_otros[df_otros[col_tecnico] == tec]
            # Ordenar barrios por donde el técnico tiene más trabajo originalmente
            barrios_prioritarios = grupo_tec[col_barrio].value_counts().index.tolist()
            
            acumulado_tec = []
            contador = 0
            
            for barrio in barrios_prioritarios:
                if contador >= 50: break
                
                # Buscar todas las pólizas disponibles de ese barrio (que no hayan sido tomadas)
                pólizas_barrio = df_otros[
                    (df_otros[col_barrio] == barrio) & 
                    (~df_otros.index.isin(pólizas_asignadas_ids))
                ].sort_values(by=[col_ciclo, col_direccion])
                
                espacio_en_cupo = 50 - contador
                toma_barrio = pólizas_barrio.head(espacio_en_cupo)
                
                if not toma_barrio.empty:
                    acumulado_tec.append(toma_barrio)
                    pólizas_asignadas_ids.update(toma_barrio.index)
                    contador += len(toma_barrio)
            
            if acumulado_tec:
                lista_rutas.append(pd.concat(acumulado_tec))

        df_resultado = pd.concat([df_ph_final] + lista_rutas, ignore_index=True)

        # --- VISUALIZACIÓN ---
        tab1, tab2 = st.tabs(["📋 Tabla de Asignación", "📊 Dashboard"])

        with tab1:
            st.success(f"✅ Optimización: Barrios como BELLARENA ahora se asignan prioritariamente a un solo técnico.")
            st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
            st.sidebar.download_button("📥 Descargar Reporte", data=output.getvalue(), file_name="Ruta_Concentrada.xlsx")

        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🏆 Top 10 Técnicos (Deuda)")
                resumen = df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).head(10).reset_index()
                resumen.columns = ["Técnico", "Deuda Total"]
                resumen["Deuda Total"] = resumen["Deuda Total"].apply(lambda x: f"$ {x:,.0f}")
                st.table(resumen)
            with c2:
                st.subheader("📍 Barrios por Técnico")
                # Gráfica para ver cuántos barrios tiene cada técnico (lo ideal es 1 o 2)
                barrios_por_tec = df_resultado.groupby(col_tecnico)[col_barrio].nunique().reset_index()
                fig = px.bar(barrios_por_tec, x=col_tecnico, y=col_barrio, labels={col_barrio: "Cant. Barrios"})
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
