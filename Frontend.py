# g:\TCC\Teste.py (Com correção no eixo de horas e legendas horizontais)

import streamlit as st
import pandas as pd
import altair as alt
import requests
# Removido 'time' pois não é mais necessário importar separadamente aqui
from datetime import datetime

# --- Configurações ---
st.set_page_config(page_title="Dashboard de Consumo", layout="wide")
st.title("📊 Dashboard de Consumo de Energia")

# URL da sua API (endpoint de busca)
API_URL_BUSCAR = "http://localhost:8000/consumo/buscar"
# Opções de aparelhos (pode vir de uma API ou ser fixa)
DEVICE_OPTIONS = ["Geladeira", "Ar-condicionado", "TV", "Microondas", "Chuveiro", "Computador", "Outro"]

# --- Função para Carregar Dados da API ---
def load_data(selected_devices, selected_date):
    """Busca dados da API para os aparelhos e data selecionados."""
    all_data = []
    if not selected_devices:
        st.warning("👈 Por favor, selecione pelo menos um aparelho.")
        return pd.DataFrame() # Retorna DataFrame vazio

    # Mostra spinner enquanto busca
    with st.spinner(f"Buscando dados para {len(selected_devices)} aparelho(s) em {selected_date}..."):
        for device in selected_devices:
            params = {"aparelho": device, "data": str(selected_date)}
            try:
                # Usa o endpoint GET /consumo/buscar
                response = requests.get(API_URL_BUSCAR, params=params, timeout=15) # Adiciona timeout
                response.raise_for_status() # Levanta erro para status 4xx/5xx
                data = response.json()
                if data: # Verifica se a API retornou dados
                    # Adiciona os dados encontrados à lista geral
                    all_data.extend(data)
                # else:
                    # Opcional: Informar se não achou dados para um aparelho específico
                    # st.caption(f"Nenhum dado encontrado para {device} em {selected_date}.")

            except requests.exceptions.Timeout:
                 st.error(f"Erro de Timeout ao buscar dados para {device}. A API demorou muito para responder.")
                 return pd.DataFrame() # Retorna vazio em caso de erro crítico
            except requests.exceptions.RequestException as e:
                st.error(f"Erro ao conectar com a API para '{device}': {e}")
                st.error(f"Verifique se a API está rodando em {API_URL_BUSCAR.rsplit('/', 2)[0]} e acessível.")
                return pd.DataFrame() # Retorna vazio em caso de erro crítico
            except Exception as e:
                st.error(f"Erro inesperado ao processar dados para '{device}': {e}")
                return pd.DataFrame() # Retorna vazio em caso de erro crítico

    if not all_data:
        # Nenhuma informação encontrada para *nenhum* dos aparelhos selecionados
        return pd.DataFrame() # Retorna DataFrame vazio

    # Cria o DataFrame final
    df = pd.DataFrame(all_data)

    # --- Tratamento e Conversão de Tipos ---
    try:
        # --- CORREÇÃO APLICADA AQUI ---
        # Converte 'hora' para objeto datetime completo. Altair usará isso para o eixo temporal.
        # A formatação do eixo no gráfico cuidará de mostrar apenas HH:MM.
        df["hora"] = pd.to_datetime(df["hora"], format="%H:%M")
        # --- FIM DA CORREÇÃO ---

        # Converte 'consumo' para numérico, tratando possíveis erros
        df["consumo"] = pd.to_numeric(df["consumo"], errors='coerce')
        # Converte 'data' para objeto date
        df["data"] = pd.to_datetime(df["data"]).dt.date
        # Remove linhas onde o consumo não pôde ser convertido (NaN)
        df.dropna(subset=['consumo'], inplace=True)
    except Exception as e:
        st.error(f"Erro ao converter tipos de dados do DataFrame: {e}")
        return pd.DataFrame()

    return df

# --- Função para Classificar Período do Dia ---
# Esta função agora precisa receber um objeto datetime, não time
def classify_period(datetime_obj):
    """Classifica um objeto datetime em períodos do dia."""
    hour = datetime_obj.hour # Extrai a hora do datetime
    if 0 <= hour < 6: return "Madrugada (00-06)"
    elif 6 <= hour < 12: return "Manhã (06-12)"
    elif 12 <= hour < 18: return "Tarde (12-18)"
    else: return "Noite (18-24)"

# --- Interface do Usuário (Sidebar para Inputs) ---
with st.sidebar:
    st.header("Filtros")
    # Seleção Múltipla de Aparelhos
    aparelhos_selecionados = st.multiselect(
        "Selecione um ou mais aparelhos:",
        options=DEVICE_OPTIONS,
        default=DEVICE_OPTIONS[0] if DEVICE_OPTIONS else None # Padrão: primeiro da lista
    )
    # Seleção de Data
    data_selecionada = st.date_input(
        "Selecione a data:",
        value=datetime.now().date() # Padrão: data de hoje
    )
    # Botão para iniciar a consulta (opcional, pode rodar automaticamente)
    # consultar = st.button("Consultar Dados")

# --- Carregar e Processar Dados ---
# if consultar: # Descomente esta linha e a do botão se quiser rodar só ao clicar
df_consumo = load_data(aparelhos_selecionados, data_selecionada)

# --- Exibir Resultados (Apenas se houver dados) ---
if not df_consumo.empty:
    st.success(f"Dados carregados para **{len(aparelhos_selecionados)}** aparelho(s) em **{data_selecionada.strftime('%d/%m/%Y')}**.")

    # Adiciona coluna de período e ordena por hora para gráficos de linha
    # A coluna 'hora' agora é datetime, então classify_period funciona
    df_consumo['periodo'] = df_consumo['hora'].apply(classify_period)
    # Ordenar por datetime completo funciona como esperado
    df_consumo = df_consumo.sort_values(by='hora')

    # --- KPIs / Métricas Resumidas ---
    st.header("Resumo Geral")
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

    total_consumo_geral = df_consumo['consumo'].sum()
    media_consumo_geral = df_consumo['consumo'].mean()
    aparelho_maior_consumo_total = df_consumo.groupby('aparelho')['consumo'].sum().idxmax()

    col_kpi1.metric("Consumo Total (Geral)", f"{total_consumo_geral:.3f} kWh")
    col_kpi2.metric("Consumo Médio Horário (Geral)", f"{media_consumo_geral:.3f} kWh")
    col_kpi3.metric("Aparelho de Maior Consumo Total", aparelho_maior_consumo_total)

    st.subheader("Picos de Consumo (Geral)")
    try:
        max_row = df_consumo.loc[df_consumo['consumo'].idxmax()]
        min_row = df_consumo.loc[df_consumo['consumo'].idxmin()]
        # max_row['hora'] agora é datetime, formatamos para exibição
        st.info(f"🔺 **Pico Máximo:** {max_row['consumo']:.3f} kWh às {max_row['hora'].strftime('%H:%M')} (Aparelho: {max_row['aparelho']})")
        # min_row['hora'] agora é datetime, formatamos para exibição
        st.info(f"🔻 **Pico Mínimo:** {min_row['consumo']:.3f} kWh às {min_row['hora'].strftime('%H:%M')} (Aparelho: {min_row['aparelho']})")
    except Exception as e:
        st.warning(f"Não foi possível calcular os picos: {e}")


    st.markdown("---") # Linha divisória

    # --- Abas para Diferentes Visualizações ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Consumo Horário (Linha)",
        "📊 Comparativo por Aparelho",
        "📉 Distribuição Horária (Histograma)",
        "📅 Consumo por Período"
    ])

    # --- Aba 1: Gráfico de Linha ---
    with tab1:
        st.subheader("Consumo Horário Detalhado")
        chart_line = alt.Chart(df_consumo).mark_line(point=True).encode(
            # 'hora:T' funciona corretamente com datetime completo
            x=alt.X('hora:T', title='Hora do Dia', axis=alt.Axis(format="%H:%M")),
            y=alt.Y('consumo:Q', title='Consumo (kWh)', axis=alt.Axis(format=".3f")),
            # Legenda horizontal (já estava ok)
            color=alt.Color('aparelho:N', title="Aparelho",
                            legend=alt.Legend(
                                orient="bottom"
                            )),
            tooltip=[
                # Formatamos a hora no tooltip também
                alt.Tooltip('hora:T', title='Hora', format="%H:%M"),
                alt.Tooltip('consumo:Q', title='Consumo (kWh)', format=".3f"),
                alt.Tooltip('aparelho:N', title='Aparelho')
            ]
        ).properties(
            title=f'Consumo ao longo do dia {data_selecionada.strftime("%d/%m/%Y")}'
        ).interactive()
        st.altair_chart(chart_line, use_container_width=True)

    # --- Aba 2: Gráfico de Barras Comparativo por Aparelho ---
    with tab2:
        st.subheader("Consumo Total por Aparelho")
        df_total_aparelho = df_consumo.groupby('aparelho', as_index=False)['consumo'].sum()

        chart_bar_aparelho = alt.Chart(df_total_aparelho).mark_bar().encode(
            x=alt.X('aparelho:N', title='Aparelho', sort='-y'),
            y=alt.Y('consumo:Q', title='Consumo Total (kWh)'),
            # Legenda horizontal (já estava ok)
            color=alt.Color('aparelho:N', title="Aparelho",
                            legend=alt.Legend(
                                orient="bottom"
                            )),
            tooltip=[
                alt.Tooltip('aparelho:N', title='Aparelho'),
                alt.Tooltip('consumo:Q', title='Consumo Total (kWh)', format=".3f")
            ]
        ).properties(
            title=f'Comparativo de Consumo Total por Aparelho em {data_selecionada.strftime("%d/%m/%Y")}'
        )
        st.altair_chart(chart_bar_aparelho, use_container_width=True)

    # --- Aba 3: Histograma de Distribuição ---
    with tab3:
        st.subheader("Distribuição de Níveis de Consumo Horário")
        if len(aparelhos_selecionados) > 1:
            device_for_hist = st.selectbox(
                "Selecione um aparelho para ver o histograma:",
                aparelhos_selecionados,
                key="hist_device_select"
            )
            df_hist = df_consumo[df_consumo['aparelho'] == device_for_hist]
        elif len(aparelhos_selecionados) == 1:
            device_for_hist = aparelhos_selecionados[0]
            df_hist = df_consumo
            st.write(f"Mostrando histograma para: **{device_for_hist}**")
        else:
            df_hist = pd.DataFrame()

        if not df_hist.empty:
            chart_hist = alt.Chart(df_hist).mark_bar().encode(
                alt.X("consumo:Q", bin=alt.Bin(maxbins=10), title="Nível de Consumo (kWh)"),
                alt.Y('count()', title='Quantidade de Horas'),
                tooltip=[
                    alt.Tooltip("consumo:Q", bin=True, title="Faixa de Consumo"),
                    alt.Tooltip('count()', title='Qtd. Horas')
                ]
            ).properties(
                title=f'Frequência de Níveis de Consumo para {device_for_hist} em {data_selecionada.strftime("%d/%m/%Y")}'
            )
            st.altair_chart(chart_hist, use_container_width=True)
        elif aparelhos_selecionados:
             st.info(f"Não há dados suficientes para gerar o histograma para {device_for_hist}.")

    # --- Aba 4: Gráfico de Barras por Período do Dia ---
    with tab4:
        st.subheader("Consumo Médio por Período do Dia")
        df_periodo = df_consumo.groupby(['periodo', 'aparelho'], as_index=False)['consumo'].mean()
        period_order = ["Madrugada (00-06)", "Manhã (06-12)", "Tarde (12-18)", "Noite (18-24)"]

        chart_bar_periodo = alt.Chart(df_periodo).mark_bar().encode(
            x=alt.X('aparelho:N', title='Aparelho'),
            y=alt.Y('consumo:Q', title='Consumo Médio (kWh)'),
            # Legenda horizontal (já estava ok)
            color=alt.Color('aparelho:N', title='Aparelho',
                            legend=alt.Legend(
                                orient="bottom"
                            )),
            column=alt.Column(
                'periodo:N',
                title='Período do Dia',
                sort=period_order,
                header=alt.Header(titleOrient="bottom", labelOrient="top")
            ),
            tooltip=[
                alt.Tooltip('periodo:N', title='Período'),
                alt.Tooltip('aparelho:N', title='Aparelho'),
                alt.Tooltip('consumo:Q', title='Consumo Médio (kWh)', format=".3f")
            ]
        ).properties(
            title=f'Comparativo de Consumo Médio por Período em {data_selecionada.strftime("%d/%m/%Y")}'
        )
        st.altair_chart(chart_bar_periodo, use_container_width=True)

# --- Mensagem se nenhum dado foi encontrado após a consulta ---
elif aparelhos_selecionados:
    st.warning(f"Não foram encontrados dados de consumo para os aparelhos selecionados na data {data_selecionada.strftime('%d/%m/%Y')}.")
    st.info("Verifique se há dados no MongoDB para essa combinação ou se a API está funcionando corretamente.")

# --- Rodapé ---
st.markdown("---")
st.caption("Dashboard desenvolvido para análise de consumo de energia.")
