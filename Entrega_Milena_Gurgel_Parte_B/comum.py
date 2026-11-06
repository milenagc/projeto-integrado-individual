from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import estatisticas as est
import etl

PASTA = Path(__file__).parent
ESTADOS_PERSONA = ["BA", "PE", "AM", "CE"]  
FAIXAS = ["14 a 24 anos", "25 a 49 anos", "50 anos ou mais"]
CORES_SEXO = {"Mulheres": "#8E44AD", "Homens": "#2E86C1"}
ROTULO_HORAS = "Horas semanais"


def fmt(valor, casas: int = 1) -> str:
    """16.75 -> '16,8' (padrão brasileiro)."""
    return f"{valor:.{casas}f}".replace(".", ",")


@st.cache_data
def _base_padrao(nome_arquivo: str) -> pd.DataFrame:
    return etl.carregar(PASTA / "dados_tratados" / nome_arquivo)


def carregar_dados(numero_tabela: int, arquivo_padrao: str, chave: str) -> pd.DataFrame:
    st.sidebar.markdown("### Base de dados")
    enviado = st.sidebar.file_uploader(
        f"Upload da Tabela {numero_tabela} (SIDRA) – CSV ou XLSX",
        type=["csv", "xlsx"], key=chave,
        help="Aceita o CSV (BR) baixado do SIDRA ou o arquivo já tratado pelo etl.py.",
    )
    if enviado is None:
        st.sidebar.caption(f"Usando a base padrão: Tabela {numero_tabela} – IBGE/SIDRA.")
        return _base_padrao(arquivo_padrao)
    try:
        df = etl.carregar(enviado)
    except Exception as erro:  
        st.sidebar.error(f"Não foi possível ler o arquivo ({erro}). Usando a base padrão.")
        return _base_padrao(arquivo_padrao)
    tabelas = df["tabela"].dropna().unique()
    if len(tabelas) == 1 and int(tabelas[0]) != numero_tabela:
        st.sidebar.warning(f"O arquivo é da Tabela {int(tabelas[0])}, mas esta seção usa a "
                           f"Tabela {numero_tabela}. Usando a base padrão.")
        return _base_padrao(arquivo_padrao)
    if df.empty:
        st.sidebar.warning("O arquivo não tem valores numéricos. Usando a base padrão.")
        return _base_padrao(arquivo_padrao)
    st.sidebar.success(f"Arquivo carregado: {enviado.name} ({len(df)} linhas)")
    return df



def filtros(df: pd.DataFrame, varios_anos: bool = False) -> dict:
    """Barra lateral: Estados, Faixa etária e Ano (requisitos da persona)."""
    st.sidebar.markdown("### Filtros")
    ufs = sorted(df.loc[df["nivel"] == "UF", "sigla_uf"].unique())

    so_persona = st.sidebar.checkbox("Somente estados da persona (BA, PE, AM, CE)", key="so_persona")
    if so_persona:
        estados = [uf for uf in ESTADOS_PERSONA if uf in ufs]
        st.sidebar.multiselect("Estados (UF)", ufs, default=estados, disabled=True, key="uf_travado")
    else:
        estados = st.sidebar.multiselect("Estados (UF)", ufs, default=ufs, key="ufs")
    if not estados:
        st.sidebar.warning("Nenhum estado selecionado: mostrando todos.")
        estados = ufs

    tem_idade = (df["tipo_recorte"] == "Grupo de idade").any()
    faixa = st.sidebar.selectbox(
        "Faixa etária", ["Todas"] + FAIXAS, key="faixa", disabled=not tem_idade,
        help=None if tem_idade else "A tabela do IBGE desta seção não tem recorte por idade.",
    )
    if not tem_idade:
        st.sidebar.caption("ℹ️ A tabela do IBGE desta seção não separa por faixa etária. "
                           "O filtro funciona na Parte E (Tabela 9378).")

    anos_disp = sorted(df["ano"].unique())
    if varios_anos:
        anos = st.sidebar.multiselect("Anos", anos_disp, default=anos_disp, key="anos")
        anos = sorted(anos) or anos_disp
    else:
        anos = [st.sidebar.selectbox("Ano", anos_disp, index=len(anos_disp) - 1, key="ano")]
    st.sidebar.caption("Não há dados de 2020 e 2021: o IBGE não divulgou este módulo na pandemia.")

    return {"estados": estados, "faixa": faixa, "anos": anos}


def aplicar_filtros(df: pd.DataFrame, f: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (linhas das UFs filtradas, linhas do Brasil) já filtradas por ano e faixa."""
    base = df[df["ano"].isin(f["anos"])]
    if (base["tipo_recorte"] == "Grupo de idade").any():
        faixas = FAIXAS if f["faixa"] == "Todas" else [f["faixa"]]
        base = base[base["recorte"].isin(faixas)]
    ufs = base[(base["nivel"] == "UF") & (base["sigla_uf"].isin(f["estados"]))]
    br = base[base["nivel"] == "BR"]
    return ufs, br


def bloco_estatistico(dados: pd.DataFrame, titulo_grupo: str = "Grupo") -> None:
    """
    dados: colunas 'sigla_uf', 'grupo', 'valor' (um valor por UF e grupo).
    Mostra tabela com todas as medidas, boxplot interativo e a análise de outliers.
    """
    grupos = list(dict.fromkeys(dados["grupo"]))
    resumos = {g: est.resumo_estatistico(dados.loc[dados["grupo"] == g, "valor"]) for g in grupos}

    tabela = None
    for g, r in resumos.items():
        t = est.tabela_resumo(r).rename(columns={"Valor": g}).set_index("Medida")
        tabela = t if tabela is None else tabela.join(t)
    st.markdown("**Medidas de tendência central e dispersão (entre as UFs selecionadas)**")
    st.dataframe(tabela, width="stretch")
    st.caption("Variância e desvio padrão populacionais (todas as UFs selecionadas). "
               "Outliers pela regra 1,5 × IQR.")

    fig = px.box(dados, x="grupo", y="valor", points="all", hover_name="sigla_uf",
                 color="grupo", labels={"grupo": titulo_grupo, "valor": ROTULO_HORAS})
    fig.update_layout(showlegend=False, title="Boxplot – distribuição das horas entre as UFs")
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Outliers e efeito na média × mediana**")
    algum = False
    for g, r in resumos.items():
        if not r:
            continue
        sub = dados[dados["grupo"] == g]
        fora = est.outliers(sub, "valor")
        if fora.empty:
            continue
        algum = True
        lista = ", ".join(f"{u} ({fmt(v)} h)" for u, v in zip(fora["sigla_uf"], fora["valor"]))
        sem = sub.drop(fora.index)["valor"]
        st.write(f"- **{g}**: outlier(s) {lista}. Com eles, média = {fmt(r['media'], 2)} h e "
                 f"mediana = {fmt(r['mediana'], 2)} h. Sem eles, a média seria "
                 f"{fmt(sem.mean(), 2)} h: a mediana quase não muda, porque é robusta a "
                 f"valores extremos, enquanto a média é puxada por eles.")
    if not algum:
        st.write("- Nenhuma UF ficou fora do intervalo [Q1 − 1,5·IQR ; Q3 + 1,5·IQR] nesta seleção: "
                 "não há outliers, e por isso a média e a mediana ficam próximas.")
    for g, r in resumos.items():
        if r and abs(r["media"] - r["mediana"]) >= 0.3:
            lado = "acima" if r["media"] > r["mediana"] else "abaixo"
            st.write(f"- **{g}**: a média está {lado} da mediana "
                     f"({fmt(r['media'], 2)} × {fmt(r['mediana'], 2)} h), sinal de assimetria: "
                     f"algumas UFs com valores {'altos' if lado == 'acima' else 'baixos'} deslocam a média.")


def kpis(itens: list[tuple]) -> None:
    """itens: lista de (rótulo, valor, delta opcional, ajuda opcional)."""
    colunas = st.columns(len(itens))
    for coluna, item in zip(colunas, itens):
        rotulo, valor, *resto = item
        delta = resto[0] if len(resto) > 0 else None
        ajuda = resto[1] if len(resto) > 1 else None
        coluna.metric(rotulo, valor, delta, help=ajuda, delta_color="off")


NOTICIAS = {
    "carga_mental": [
        ("Pesquisa com 1.078 mulheres: sobrecarga doméstica é a 2ª maior causa de descontentamento",
         "Brasil de Fato", "https://www.brasildefato.com.br/?p=618822"),
        ("Burnout e carga mental: uma comparação à luz do Dia Internacional da Mulher",
         "A Gazeta", "https://www.agazeta.com.br/colunas/gina-strozzi/burnout-e-carga-mental-uma-comparacao-a-luz-do-dia-internacional-da-mulher-0322"),
        ("Trabalho doméstico não remunerado e saúde mental (artigo científico, 2023)",
         "Revista de Saúde Pública / SciELO", "https://scielosp.org/pdf/rsp/2023.v57/31/pt"),
    ],
    "economia_cuidado": [
        ("Economia do cuidado: mulheres são responsáveis por mais de 75% do trabalho não remunerado",
         "Forbes Mulher", "https://forbes.com.br/forbes-mulher/2023/11/economia-do-cuidado-mulheres-sao-responsaveis-por-mais-de-75-do-trabalho-nao-remunerado/"),
        ("Economia do cuidado: um trabalho invisível e não remunerado das mulheres",
         "O Povo+", "https://mais.opovo.com.br/reportagens-especiais/mulheres-e-cuidado-economia-sociedade/2024/06/25/economia-do-cuidado-um-trabalho-invisivel-e-nao-remunerado-das-mulheres.html"),
        ("Debatedores defendem inclusão da “economia do cuidado” nas contas do PIB",
         "Agência Câmara", "https://www.camara.leg.br/noticias/1026290-debatedores-defendem-inclusao-da-economia-do-cuidado-nas-contas-do-pib/"),
    ],
    "ibge": [
        ("Em média, mulheres dedicam 10,4 horas por semana a mais que os homens aos afazeres domésticos",
         "Agência IBGE Notícias", "https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/27877-em-media-mulheres-dedicam-10-4-horas-por-semana-a-mais-que-os-homens-aos-afazeres-domesticos-ou-ao-cuidado-de-pessoas"),
        ("PNAD: mulheres gastam quase o dobro de tempo no serviço doméstico",
         "Agência Brasil", "https://agenciabrasil.ebc.com.br/geral/noticia/2023-08/pnad-mulheres-gastam-quase-o-dobro-de-tempo-no-servico-domestico"),
    ],
}


def infografico(horas_mulheres: float, horas_homens: float, ano: int, local: str = "Brasil") -> None:
    """Infográfico gerado a partir dos dados (não depende de imagem externa)."""
    dif = horas_mulheres - horas_homens
    dias = dif * 52 / 24
    st.markdown(
        f"""
<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 16px">
  <div style="flex:1;min-width:180px;padding:16px;border-radius:12px;background:{CORES_SEXO['Mulheres']};color:#fff">
    <div style="font-size:14px">👩 Mulheres – {local}, {ano}</div>
    <div style="font-size:34px;font-weight:700">{fmt(horas_mulheres)} h/semana</div></div>
  <div style="flex:1;min-width:180px;padding:16px;border-radius:12px;background:{CORES_SEXO['Homens']};color:#fff">
    <div style="font-size:14px">👨 Homens – {local}, {ano}</div>
    <div style="font-size:34px;font-weight:700">{fmt(horas_homens)} h/semana</div></div>
  <div style="flex:1;min-width:180px;padding:16px;border-radius:12px;background:#F4D03F;color:#222">
    <div style="font-size:14px">⏱️ Diferença em um ano</div>
    <div style="font-size:34px;font-weight:700">≈ {fmt(dias, 0)} dias</div>
    <div style="font-size:12px">{fmt(dif)} h/semana × 52 semanas ÷ 24 h</div></div>
</div>""",
        unsafe_allow_html=True,
    )


def secao_noticias(temas: list[str], prefixo_imagens: str) -> None:
    """Bloco de notícias reais + imagens ilustrativas da pasta imagens/."""
    st.subheader("📰 Notícias e contexto: Carga Mental Feminina e Economia do Cuidado")
    colunas = st.columns(len(temas))
    titulos = {"carga_mental": "Carga Mental Feminina", "economia_cuidado": "Economia do Cuidado",
               "ibge": "Dados oficiais (IBGE)"}
    for coluna, tema in zip(colunas, temas):
        with coluna:
            st.markdown(f"**{titulos[tema]}**")
            for titulo, fonte, url in NOTICIAS[tema]:
                st.markdown(f"- [{titulo}]({url}) — *{fonte}*")

    imagens = sorted((PASTA / "imagens").glob(f"{prefixo_imagens}*.*")) + \
        sorted((PASTA / "imagens").glob("geral*.*"))
    imagens = [i for i in imagens if i.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    if imagens:
        imagens = imagens[:3]
        colunas = st.columns(3)
        posicoes = [1] if len(imagens) == 1 else range(len(imagens))  
        for pos, img in zip(posicoes, imagens):
            legenda = img.stem.split("__")[-1].replace("_", " ") if "__" in img.stem else img.stem
            colunas[pos].image(str(img), caption=legenda, width="stretch")
    else:
        st.info(f"Adicione imagens ilustrativas em imagens/ com nome começando por "
                f"'{prefixo_imagens}' ou 'geral' (ex.: {prefixo_imagens}__Mulher_cuidando_da_casa.jpg).")
