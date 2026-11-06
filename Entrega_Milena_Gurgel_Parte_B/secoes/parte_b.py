import plotly.express as px
import streamlit as st

import comum as c

CORES = ["Branca", "Preta", "Parda"]


def render():
    st.header("B · Horas por gênero e raça")
    st.caption("Responsável: Milena Gurgel · Fonte: IBGE – PNAD Contínua, Tabela 9379")

    df = c.carregar_dados(9379, "tabela_9379_cor_raca_tratada.csv", "up_b")
    f = c.filtros(df)
    ufs, br = c.aplicar_filtros(df, f)
    ano = f["anos"][0]

    ufs = ufs[ufs["sexo"].isin(["Mulheres", "Homens"]) & ufs["recorte"].isin(CORES)].copy()
    nomes = {("Mulheres", "Branca"): "Mulheres brancas", ("Mulheres", "Preta"): "Mulheres pretas",
             ("Mulheres", "Parda"): "Mulheres pardas", ("Homens", "Branca"): "Homens brancos",
             ("Homens", "Preta"): "Homens pretos", ("Homens", "Parda"): "Homens pardos"}
    ufs["grupo"] = [nomes[(s, r)] for s, r in zip(ufs["sexo"], ufs["recorte"])]
    ordem = ["Mulheres pretas", "Mulheres pardas", "Mulheres brancas",
             "Homens pretos", "Homens pardos", "Homens brancos"]
    medias = ufs.groupby("grupo")["horas"].mean().reindex(ordem)

    c.kpis([(g, f"{c.fmt(medias[g])} h") for g in ordem[:3]])
    c.kpis([(g, f"{c.fmt(medias[g])} h") for g in ordem[3:]])
    c.kpis([
        ("Mulheres pretas − brancas", f"{c.fmt(medias['Mulheres pretas'] - medias['Mulheres brancas'])} h"),
        ("Mulheres pardas − brancas", f"{c.fmt(medias['Mulheres pardas'] - medias['Mulheres brancas'])} h"),
        ("Mulheres pretas − homens brancos",
         f"{c.fmt(medias['Mulheres pretas'] - medias['Homens brancos'])} h"),
    ])
    st.caption("Médias das UFs selecionadas. O IBGE separa as categorias Preta e Parda.")

    resumo = medias.reset_index()
    resumo.columns = ["grupo", "horas"]
    resumo["sexo"] = resumo["grupo"].str.split().str[0]
    fig = px.bar(resumo, x="grupo", y="horas", color="sexo", text_auto=".1f",
                 color_discrete_map=c.CORES_SEXO,
                 labels={"grupo": "Gênero e raça", "horas": c.ROTULO_HORAS, "sexo": "Sexo"},
                 title=f"Horas semanais por gênero e raça – média das UFs selecionadas, {ano}")
    st.plotly_chart(fig, width="stretch")

    sexo_uf = st.radio("Comparar por estado:", ["Mulheres", "Homens"], horizontal=True, key="sexo_b")
    por_uf = ufs[ufs["sexo"] == sexo_uf]
    fig2 = px.bar(por_uf, x="sigla_uf", y="horas", color="recorte", barmode="group",
                  labels={"sigla_uf": "Estado (UF)", "horas": c.ROTULO_HORAS, "recorte": "Cor ou raça"},
                  title=f"{sexo_uf}: horas semanais por cor ou raça e estado – {ano}")
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Análise estatística")
    dados = ufs[["sigla_uf", "grupo", "horas"]].rename(columns={"horas": "valor"})
    dados["grupo"] = dados["grupo"].astype("category").cat.set_categories(ordem)
    dados = dados.sort_values("grupo")
    dados["grupo"] = dados["grupo"].astype(str)
    c.bloco_estatistico(dados, "Gênero e raça")

    st.subheader("Resposta para a persona")
    brv = br[br["recorte"].isin(CORES) & br["sexo"].isin(["Mulheres", "Homens"])]
    tabela_br = brv.pivot_table(index="recorte", columns="sexo", values="horas").reindex(CORES)
    tabela_br["Diferença (M − H)"] = tabela_br["Mulheres"] - tabela_br["Homens"]
    st.markdown(f"**Brasil, {ano} (valor oficial IBGE)**")
    st.dataframe(tabela_br.style.format("{:.1f}"), width="stretch")
    dif_genero = medias[ordem[:3]].mean() - medias[ordem[3:]].mean()
    dif_raca_m = medias[ordem[:3]].max() - medias[ordem[:3]].min()
    mais_carga = medias.idxmax()
    st.markdown(
        f"Nas UFs selecionadas, mulheres pretas dedicam **{c.fmt(medias['Mulheres pretas'])} h**, "
        f"mulheres pardas **{c.fmt(medias['Mulheres pardas'])} h** e mulheres brancas "
        f"**{c.fmt(medias['Mulheres brancas'])} h** por semana. Entre os homens, os valores vão de "
        f"{c.fmt(medias[ordem[3:]].min())} a {c.fmt(medias[ordem[3:]].max())} h. "
        f"A diferença entre os gêneros (≈ {c.fmt(dif_genero)} h) é "
        f"{'muito maior' if dif_genero > 2 * dif_raca_m else 'comparável'} à diferença entre raças "
        f"entre as mulheres (≈ {c.fmt(dif_raca_m)} h). O grupo com maior carga é "
        f"**{mais_carga}** — público prioritário para as políticas de cuidado."
    )

    c.secao_noticias(["carga_mental", "economia_cuidado", "ibge"], "parte_b")
