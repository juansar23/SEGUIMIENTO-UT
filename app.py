import streamlit as st
import pandas as pd
import plotly.express as px
import io

# Configuración de la página
st.set_page_config(page_title="Dashboard Ejecutivo UT", layout="wide")

st.title("📊 Dashboard Ejecutivo - Optimización Logística")
st.markdown("---")

# --- SIDEBAR (Barra Lateral) ---
st.sidebar.header("⚙️ Configuración")
# Se incluyen múltiples tipos para asegurar que Windows muestre los archivos .xls
archivo = st.sidebar.file_uploader("Sube el archivo de Seguimiento", type=["xls", "xlsx", "xlsm", "xlsb"])

# Nombres de las columnas ajustados
col_barrio = "BARRIO"
col_ciclo = "CICLO_FACTURACION"  # Ajustado según tu imagen
col_direccion = "DIRECCION"
col_tecnico = "TECNICOS_INTEGRALES"
col_deuda = "DEUDA_TOTAL"

if archivo:
    try:
        # 1. LECTURA DE DATOS (Soporte para .xls antiguo y .xlsx moderno)
        if archivo.name.lower().endswith(".xls"):
            df = pd.read_excel(archivo, engine="xlrd")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.str.strip()
        
        # Validar existencia de columnas
        cols_necesarias = [col_tecnico, col_deuda, col_barrio, col_ciclo, col_direccion]
        for c in cols_necesarias:
            if c not in df.columns:
                st.error(f"❌ No se encontró la columna: {c}")
                st.stop()

        # Estandarizar textos y limpiar deuda
        for col in [col_tecnico, col_barrio, col_ciclo, col_direccion]:
            df[col] = df[col].astype(str).str.strip()

        df["_deuda_num"] = (
            df[col_deuda].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(".", "", regex=False).str.strip()
        )
        df["_deuda_num"] = pd.to_numeric(df["_deuda_num"], errors="coerce").fillna(0)

        # --- FILTROS EN SIDEBAR ---
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros")
        ciclos_disponibles = sorted(df[col_ciclo].unique())
        ciclos_sel = st.sidebar.multiselect("Filtrar por Ciclo", ciclos_disponibles, default=ciclos_disponibles)
        
        df_filtrado = df[df[col_ciclo].isin(ciclos_sel)].copy()

        # --- LÓGICA DE SEGMENTACIÓN (PH vs RUTA) ---
        unidades_ph = [
            "ITA SUSPENSION BQ 15 PH", "ITA SUSPENSION BQ 31 PH", 
            "ITA SUSPENSION BQ 32 PH", "ITA SUSPENSION BQ 34 PH", 
            "ITA SUSPENSION BQ 35 PH", "ITA SUS-PENSION BQ 36 PH", 
            "ITA SUSPENSION BQ 37 PH"
        ]

        # Lógica PH: Top 50 por mayor deuda
        df_ph = df_filtrado[df_filtrado[col_tecnico].isin(unidades_ph)].copy()
        df_ph_final = df_ph.sort_values(by="_deuda_num", ascending=False).groupby(col_tecnico).head(50)

        # Lógica Ruta: Ciclo -> Barrio -> Dirección
        df_otros_base = df_filtrado[~df_filtrado[col_tecnico].isin(unidades_ph)].copy()
        lista_rutas = []
        for tec, grupo in df_otros_base.groupby(col_tecnico):
            ordenado = grupo.sort_values(by=[col_ciclo, col_barrio, col_direccion])
            lista_rutas.append(ordenado.head(50))
        
        df_otros_final = pd.concat(lista_rutas) if lista_rutas else pd.DataFrame()
        df_resultado = pd.concat([df_ph_final, df_otros_final], ignore_index=True)

        # --- VISUALIZACIÓN ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Pólizas Asignadas", len(df_resultado))
        col2.metric("Técnicos Activos", df_resultado[col_tecnico].nunique())
        col3.metric("Deuda Gestionada", f"${df_resultado['_deuda_num'].sum():,.0f}")

        # Gráficas
        c_left, c_right = st.columns(2)
        with c_left:
            fig_deuda = px.bar(
                df_resultado.groupby(col_tecnico)["_deuda_num"].sum().sort_values(ascending=False).reset_index(),
                x=col_tecnico, y="_deuda_num", title="Deuda por Técnico",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig_deuda, use_container_width=True)

        with c_right:
            fig_pie = px.pie(
                df_resultado[col_barrio].value_counts().head(10).reset_index(),
                names="index", values=col_barrio, title="Top 10 Barrios", hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # Tabla y Descarga
        st.subheader("📋 Detalle de Asignación")
        st.dataframe(df_resultado.drop(columns=["_deuda_num"]), use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_resultado.drop(columns=["_deuda_num"]).to_excel(writer, index=False)
        
        st.sidebar.download_button(
            "📥 Descargar Excel Optimizado",
            data=output.getvalue(),
            file_name="Reporte_UT_Final.xlsx"
        )

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Sube un archivo en el menú lateral para generar el Dashboard.")
