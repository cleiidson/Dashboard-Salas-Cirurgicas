import pandas as pd
import streamlit as st
import plotly.express as px
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurações do Streamlit
st.set_page_config(page_title="Salas Cirúrgicas", layout="wide", initial_sidebar_state="expanded")

# Função para formatar minutos em HH:MM
def formatar_tempo_minutos(minutos):
    if pd.isna(minutos):
        return "N/A"
    horas = int(minutos // 60)
    minutos_restantes = int(minutos % 60)
    return f"{horas:02d}:{minutos_restantes:02d}"

# Função para extrair nome da sala cirúrgica do campo Local de forma mais robusta
def extrair_sala(local):
    """
    Extrai o nome da sala a partir de uma string de localização.
    Assume que a sala está na última parte do caminho, ex.: "SALA CIRÚRGICA 02".
    Retorna "Desconhecida" se o valor não for uma string válida.
    """
    try:
        # Verifica se o valor é uma string válida e não está vazio
        if isinstance(local, str) and local.strip():
            # A função .split('/') retorna uma lista. Acessamos o último item com [-1].
            # .strip() é usado para remover espaços em branco extras no início e no fim.
            return local.strip('/').split('/')[-1].strip()
    except Exception as e:
        # Loga o erro, mas continua para evitar quebra do app
        logging.error(f"Erro ao extrair sala de '{local}': {e}")
    return "Desconhecida"

# Função para carregar dados
@st.cache_data
def load_data(uploaded_file):
    try:
        if uploaded_file is None:
            st.error("Nenhum arquivo foi selecionado. Por favor, carregue um arquivo .xlsx ou .csv.")
            return None
        
        file_name = uploaded_file.name.lower()
        if file_name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, usecols=['Nº', 'Status', 'Origem', 'Serviço', 'Local', 'Início Real', 'Término Real'])
        elif file_name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, usecols=['Nº', 'Status', 'Origem', 'Serviço', 'Local', 'Início Real', 'Término Real'])
        else:
            st.error(f"Formato de arquivo '{file_name}' não suportado. Use .xlsx ou .csv.")
            return None
        
        # Verifica colunas obrigatórias
        required_columns = ['Serviço', 'Local', 'Início Real', 'Término Real']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"O arquivo '{file_name}' não contém as colunas obrigatórias: {', '.join(missing_columns)}. Verifique a estrutura do arquivo.")
            return None
        
        if df.empty:
            st.error(f"O arquivo '{file_name}' está vazio. Carregue um arquivo com dados válidos.")
            return None
        
        return df
    except Exception as e:
        logging.error(f"Erro ao carregar arquivo: {e}")
        st.error(f"Erro ao carregar '{file_name}': {e}. Verifique se o arquivo está no formato correto e contém dados válidos.")
        return None

# Função para processar dados
@st.cache_data
def process_data(df):
    try:
        df = df.copy()
        
        # --- FILTRAGEM CRÍTICA ---
        # Certifique-se de que a coluna 'Status' e 'Serviço' existem e têm valores esperados
        df['Status'] = df['Status'].astype(str)
        df['Serviço'] = df['Serviço'].astype(str)

        # Filtra apenas status "Finalizada"
        df = df[df['Status'].str.lower() == 'finalizada']
        
        # Converte colunas de data
        df['Início Real'] = pd.to_datetime(df['Início Real'], errors='coerce', dayfirst=True)
        df['Término Real'] = pd.to_datetime(df['Término Real'], errors='coerce', dayfirst=True)
        
        # Extrai nome da sala cirúrgica
        df['Sala Cirúrgica'] = df['Local'].apply(extrair_sala)
        
        # Normaliza tipo de serviço
        df['Serviço'] = df['Serviço'].str.strip().str.lower()
        valid_services = ['limpeza terminal', 'limpeza concorrente']
        df = df[df['Serviço'].isin(valid_services)]
        
        if df.empty:
            st.warning("Nenhum dado válido encontrado após processamento e filtragem. Verifique se o arquivo tem 'Status' como 'Finalizada' e 'Serviço' como 'Limpeza Terminal' ou 'Limpeza Concorrente'.")
            return None
        
        # Remove linhas com datas inválidas (NaT - Not a Time)
        df.dropna(subset=['Início Real', 'Término Real'], inplace=True)

        # Calcula duração da limpeza em minutos
        df['Duração Minutos'] = (df['Término Real'] - df['Início Real']).dt.total_seconds() / 60
        df['Duração Formatada'] = df['Duração Minutos'].apply(formatar_tempo_minutos)
        
        return df
    except Exception as e:
        logging.error(f"Erro ao processar dados: {e}")
        st.error(f"Erro ao processar dados: {e}. Verifique o conteúdo do arquivo.")
        return None

# --- Título e Descrição ---
st.title("🏥 Dashboard de Salas Cirúrgicas")
st.markdown("Bem-vindo ao dashboard. Faça o upload do seu arquivo de dados para começar a análise.")

# --- Barra Lateral (Filtros) ---
st.sidebar.header("Filtros")

# Uploader de arquivo na barra lateral
uploaded_file = st.sidebar.file_uploader(
    "Carregue seu arquivo de dados (.xlsx ou .csv)",
    type=["xlsx", "csv"],
    key="file_uploader"
)

# --- Lógica Principal da Aplicação ---
if uploaded_file:
    df_raw = load_data(uploaded_file)
    
    if df_raw is not None and not df_raw.empty:
        df_processed = process_data(df_raw)
        
        if df_processed is None or df_processed.empty:
            st.warning("Dados inválidos ou colunas mal formatadas. Verifique o arquivo.")
        else:
            # Filtros de data
            data_min = df_processed['Início Real'].min().date() if not df_processed['Início Real'].isna().all() else datetime.now().date()
            data_max = df_processed['Início Real'].max().date() if not df_processed['Início Real'].isna().all() else datetime.now().date()
            data_inicio = st.sidebar.date_input("Data Início", data_min, min_value=data_min, max_value=data_max)
            data_fim = st.sidebar.date_input("Data Fim", data_max, min_value=data_min, max_value=data_max)
            
            # Filtra o DataFrame inicial com as datas
            df_interim = df_processed[(df_processed['Início Real'].dt.date >= data_inicio) & (df_processed['Início Real'].dt.date <= data_fim)]

            # Apenas se df_interim não estiver vazio, preencha a lista de salas para o multiselect
            salas_disponiveis = []
            if not df_interim.empty:
                salas_disponiveis = sorted(df_interim['Sala Cirúrgica'].dropna().unique().tolist())
            
            sala_selecionada = st.sidebar.multiselect("Selecione a(s) sala(s) cirúrgica(s)", salas_disponiveis)

            # Filtro de tipo de limpeza
            tipos_limpeza = ['Todos', 'Limpeza Terminal', 'Limpeza Concorrente']
            tipo_selecionado = st.sidebar.selectbox("Selecione o tipo de limpeza", tipos_limpeza, index=0)

            # --- APLICANDO OS FILTROS AO DATAFRAME FINAL ---
            df_final = df_interim.copy()
            
            if sala_selecionada:
                df_final = df_final[df_final['Sala Cirúrgica'].isin(sala_selecionada)]
            
            if tipo_selecionado != 'Todos':
                tipo_map = {'Limpeza Terminal': 'limpeza terminal', 'Limpeza Concorrente': 'limpeza concorrente'}
                df_final = df_final[df_final['Serviço'] == tipo_map[tipo_selecionado]]
            
            # --- FIM DA LÓGICA DE FILTRAGEM ---
            
            # Exibir conteúdo apenas se o dataframe final não estiver vazio
            if not df_final.empty:
                # --- CALCULA OS INDICADORES A PARTIR DO DATAFRAME FILTRADO ---
                st.header("📊 Indicadores")
                
                # Prepara dataframes para cada tipo de serviço a partir do df_final
                df_terminal = df_final[df_final['Serviço'] == 'limpeza terminal']
                df_concorrente = df_final[df_final['Serviço'] == 'limpeza concorrente']

                # Calcula os totais e médias
                total_terminal = len(df_terminal)
                media_terminal = df_terminal['Duração Minutos'].mean()

                total_concorrente = len(df_concorrente)
                media_concorrente = df_concorrente['Duração Minutos'].mean()
                
                # Exibe os indicadores nas colunas
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Total de Limpezas Terminais", total_terminal)
                with c2:
                    st.metric("Total de Limpezas Concorrentes", total_concorrente)
                with c3:
                    st.metric("Duração Média Terminais", formatar_tempo_minutos(media_terminal) if pd.notnull(media_terminal) else "N/A")
                with c4:
                    st.metric("Duração Média Concorrentes", formatar_tempo_minutos(media_concorrente) if pd.notnull(media_concorrente) else "N/A")
                
                # --- GRÁFICOS E TABELAS COM OS DADOS FILTRADOS ---
                st.header("📅 Limpezas por Dia")
                limpezas_por_dia_filtrado = df_final.groupby([df_final['Início Real'].dt.date, 'Serviço']).size().reset_index(name='Quantidade')
                limpezas_por_dia_filtrado['Início Real'] = pd.to_datetime(limpezas_por_dia_filtrado['Início Real'])
                
                fig1 = px.bar(
                    limpezas_por_dia_filtrado,
                    x='Início Real',
                    y='Quantidade',
                    color='Serviço',
                    barmode='group',
                    labels={"Início Real": "Dia", "Quantidade": "Número de Limpezas", "Serviço": "Tipo de Limpeza"},
                    title="Limpezas por Dia (Terminal vs Concorrente)",
                    template="plotly_white",
                    color_discrete_map={'limpeza terminal': '#1f77b4', 'limpeza concorrente': '#ff7f0e'},
                    text_auto=True
                )
                fig1.update_xaxes(tickformat="%d", tickangle=45)
                st.plotly_chart(fig1, use_container_width=True)
                
                st.header("🏥 Limpezas por Sala Cirúrgica")
                limpezas_por_sala_filtrado = df_final.groupby(['Sala Cirúrgica', 'Serviço']).size().reset_index(name='Quantidade')
                fig2 = px.bar(
                    limpezas_por_sala_filtrado,
                    x='Sala Cirúrgica',
                    y='Quantidade',
                    color='Serviço',
                    barmode='group',
                    labels={"Sala Cirúrgica": "Sala Cirúrgica", "Quantidade": "Número de Limpezas", "Serviço": "Tipo de Limpeza"},
                    title="Limpezas por Sala (Terminal vs Concorrente)",
                    template="plotly_white",
                    color_discrete_map={'limpeza terminal': '#1f77b4', 'limpeza concorrente': '#ff7f0e'},
                    text_auto=True
                )
                fig2.update_traces(textposition='auto')
                st.plotly_chart(fig2, use_container_width=True)
                
                st.header("📋 Dados Detalhados")
                display_columns = ['Nº', 'Status', 'Origem', 'Serviço', 'Sala Cirúrgica', 'Início Real', 'Término Real', 'Duração Formatada']
                available_columns = [col for col in display_columns if col in df_final.columns]
                st.dataframe(df_final[available_columns])
            else:
                st.info("Nenhum dado disponível para os filtros selecionados.")
    else:
        st.warning("O arquivo carregado está vazio ou não pôde ser processado. Verifique o formato e o conteúdo.")
else:
    st.info("Por favor, faça o upload de um arquivo para começar.")
