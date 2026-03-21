import streamlit as st
import pandas as pd
import plotly.express as px
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

# Estilo personalizado para el título
st.title("📊 Dashboard Ejecutivo - Optimización Logística")
st.markdown("---")

# --- SIDEBAR PARA CONFIGURACIÓN Y FILTROS ---
st.sidebar.header("⚙️ Configuración de Carga")
archivo = st.sidebar.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Nombres de las columnas críticas
col_barrio = "BARRIO"
col_ciclo = "CICLO"
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"

if archivo:
    try:
        # 1. LECTURA DE DATOS
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        # Limpieza inicial
        df.columns = df.columns.str.strip()
        
        # Validar columnas
        cols_necesarias = [col_tecnico, col_deuda, col_barrio, col_ciclo, col_direccion]
        for c in cols_necesarias:
            if c not in df.columns:
                st.error(f"❌ Falta la columna: {c}")
                st.stop()

        # Estandarizar textos
        for col in [col_tecnico, col_barrio, col_ciclo, col_direccion]:
            df[col] = df[col].astype(str).str.strip()

        # Limpieza de Deuda numérica
        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # --- FILTROS DINÁMICOS EN SIDEBAR ---
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros de Visualización")
        
        # Filtro de Ciclos
        todos_ciclos = sorted(df[col_ciclo].unique())
        ciclos_seleccionados = st.sidebar.multiselect("Seleccionar Ciclos", todos_ciclos, default=todos_ciclos)
        
        # Filtrar el DataFrame base según la selección del sidebar
        df_filtrado = df[df[col_ciclo].isin(ciclos_seleccionados)].copy()

        # ==========================================
        # LÓGICA DE PROCESAMIENTO (PH vs RUTA)
        # ==========================================
        unidades_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
            "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
            "ITA SUSPENSION BQ 35 PH", "ITA SUSPENSION BQ 36 PH", 
            "ITA SUSPENSION BQ 37 PH"
        ]

        # Lógica 1: PH (Top Deuda)
        df_ph = df_filtrado[df_filtrado[col_tecnico].isin(unidades_ph)].copy()
        df_ph_final = df_ph.sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        # Lógica 2: Otros (Ruta: Ciclo -> Barrio -> Dirección)
        df_otros_base = df_filtrado[~df_filtrado[col_tecnico].isin(unidades_ph)].copy()
        lista_otros = []
        for tec, grupo in df_otros_base.groupby(col_tecnico):
            # Ordenamiento solicitado por el usuario
            grupo_ordenado = grupo.sort_values(by=[col_ciclo, col_barrio, col_direccion])
            lista_otros.append(grupo_ordenado.head(50))
        
        df_otros_final = pd.concat(lista_otros) if lista_otros else pd.DataFrame()
        df_resultado = pd.concat([df_ph_final, df_otros_final], ignore_index=True)

        # ==========================================
        # DASHBOARD VISUAL (MÉTRICAS Y GRÁFICAS)
        # ==========================================
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pólizas Totales", len(df_resultado))
        m2.metric("Técnicos", df_resultado[col_tecnico].nunique())
        m3.metric("Deuda Total", f"${df_resultado['_deuda_num'].sum():,.0f}")
        m4.metric("Barrios Impactados", df_resultado[col_barrio].nunique())

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("💰 Deuda por Unidad Operativa")
            fig_deuda = px.bar(
                df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).reset_index(),
                x=col_tecnico, y="_deuda_num",
                color="_deuda_num", color_continuous_scale="Viridis",
                labels={"_deuda_num": "Deuda Total", col_tecnico: "Técnico"}
            )
            st.plotly_chart(fig_deuda, use_container_width=True)

        with col_right:
            st.subheader("📍 Concentración por Barrio (Top 10)")
            fig_barrio = px.pie(
                df_resultado[col_barrio].value_counts().head(10).reset_index(),
                names="index", values=col_barrio,
                hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_barrio, use_container_width=True)

        # TABLA DE DATOS
        st.subheader("📋 Detalle de Asignación Optimizada")
        st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)

        # DESCARGA
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False, sheet_name="Ruta_Optimizada")
        
        st.sidebar.markdown("---")
        st.sidebar.download_button(
            label="📥 Descargar Reporte Final",
            data=output.getvalue(),
            file_name="Reporte_UT_Optimizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error en el procesamiento: {e}")
else:
    st.info("👈 Por favor, utiliza el menú lateral para subir el archivo de Seguimiento.")
