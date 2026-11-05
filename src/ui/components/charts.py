"""Componentes de visualização gráfica interativa com Plotly para clima, risco e complexidade."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.mathematics.permutations import generate_complexity_comparison_table
from src.ui.theme import RISK_COLORS_HEX

_LEVEL_COLOR_BY_STR: dict[str, str] = {
    level.value: hex_color for level, hex_color in RISK_COLORS_HEX.items()
}


def build_weather_timeline_figure(
    weather_df: pd.DataFrame,
    title: str = "Previsão Horária: Chuva e Temperatura",
) -> go.Figure:
    """Constrói figura Plotly com precipitação horária, média móvel de 3h e temperatura.

    Args:
        weather_df: DataFrame gerado por `weather_to_dataframe`.
        title: Título exibido no topo do gráfico.

    Returns:
        Instância de `go.Figure` pronta para renderização ou inspeção em testes.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if weather_df.empty:
        fig.update_layout(
            title=title,
            template="plotly_white",
            height=320,
            annotations=[
                {
                    "text": "Sem dados meteorológicos horários disponíveis.",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 13, "color": "#64748B"},
                }
            ],
        )
        return fig

    x_axis = weather_df["Hora"] if "Hora" in weather_df.columns else weather_df.index

    fig.add_trace(
        go.Bar(
            x=x_axis,
            y=weather_df["Precipitacao_mm"],
            name="Chuva (mm/h)",
            marker_color="rgba(37, 99, 235, 0.55)",
            customdata=weather_df["Prob_Chuva_Pct"]
            if "Prob_Chuva_Pct" in weather_df.columns
            else None,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Chuva: %{y:.1f} mm<br>"
                "Probabilidade: %{customdata:.0f}%<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    if "Precipitacao_Media_Movel_3h" in weather_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=weather_df["Precipitacao_Media_Movel_3h"],
                name="Média 3h (mm)",
                mode="lines",
                line={"color": "#1D4ED8", "width": 2.2, "dash": "dash"},
                hovertemplate="<b>%{x}</b><br>Média 3h: %{y:.2f} mm<extra></extra>",
            ),
            secondary_y=False,
        )

    if "Temperatura_C" in weather_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=weather_df["Temperatura_C"],
                name="Temp. (°C)",
                mode="lines",
                line={"color": "#F97316", "width": 2.2},
                hovertemplate="<b>%{x}</b><br>Temperatura: %{y:.1f} °C<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#0F172A"}},
        template="plotly_white",
        height=330,
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
            "font": {"size": 11},
        },
        margin={"l": 28, "r": 28, "t": 58, "b": 32},
    )
    fig.update_xaxes(title_text=None, tickfont={"size": 11})
    fig.update_yaxes(
        title_text="mm",
        secondary_y=False,
        rangemode="tozero",
        tickfont={"size": 11},
    )
    fig.update_yaxes(
        title_text="°C",
        secondary_y=True,
        tickfont={"size": 11},
    )

    return fig


def build_stop_risk_bar_figure(stops_df: pd.DataFrame) -> go.Figure:
    """Constrói gráfico de barras do score de risco climático por parada na ordem otimizada.

    Args:
        stops_df: DataFrame gerado por `stops_to_dataframe`.

    Returns:
        Instância de `go.Figure` com barras coloridas conforme `Nivel_Risco`.
    """
    fig = go.Figure()

    if stops_df.empty:
        fig.update_layout(
            title="Risco Climático por Parada",
            template="plotly_white",
            height=320,
        )
        return fig

    labels = [
        f"{row['Ordem']}. {row['Destinatario']}"
        for _, row in stops_df.iterrows()
    ]
    colors = [
        _LEVEL_COLOR_BY_STR.get(str(row["Nivel_Risco"]), "#64748B")
        for _, row in stops_df.iterrows()
    ]
    custom_data = list(
        zip(
            stops_df["CEP"],
            stops_df["Bairro"],
            stops_df["Distancia_Acumulada_km"],
            stops_df["Chuva_Max_mm"],
            stops_df["Nivel_Risco"],
            strict=False,
        )
    )

    fig.add_trace(
        go.Bar(
            x=labels,
            y=stops_df["Score_Risco"],
            marker_color=colors,
            text=[f"{val:.2f}" for val in stops_df["Score_Risco"]],
            textposition="outside",
            customdata=custom_data,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Risco: %{y:.2f} (%{customdata[4]})<br>"
                "CEP: %{customdata[0]} — %{customdata[1]}<br>"
                "Distância acumulada: %{customdata[2]:.1f} km<br>"
                "Chuva máx.: %{customdata[3]:.1f} mm/h<extra></extra>"
            ),
            name="Score de Risco",
        )
    )

    fig.update_layout(
        title={"text": "Risco Climático por Parada", "font": {"size": 14, "color": "#0F172A"}},
        template="plotly_white",
        height=320,
        xaxis_title=None,
        yaxis={"title": "Risco (0 a 1)", "range": [0.0, 1.15]},
        margin={"l": 28, "r": 20, "t": 48, "b": 40},
        showlegend=False,
    )

    return fig


def build_complexity_comparison_figure(max_n: int = 10) -> go.Figure:
    """Constrói gráfico comparativo em escala logarítmica entre $O(n!)$ e $O(n^2)$.

    Args:
        max_n: Número máximo de paradas $n$ para simulação combinatória.

    Returns:
        Instância de `go.Figure` comparando permutações exatas e operações heurísticas.
    """
    records = generate_complexity_comparison_table(max_n=max_n)
    n_values = [int(r["n"]) for r in records]
    factorial_ops = [int(r["permutacoes_fatorial"]) for r in records]
    quadratic_ops = [int(r["operacoes_heuristica_n2"]) for r in records]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=n_values,
            y=factorial_ops,
            mode="lines+markers",
            name="Força Bruta O(n!)",
            line={"color": "#EF4444", "width": 2.5},
            marker={"size": 7},
            hovertemplate="<b>n = %{x} paradas</b><br>Permutações (n!): %{y:,}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=n_values,
            y=quadratic_ops,
            mode="lines+markers",
            name="Heurística O(n²)",
            line={"color": "#10B981", "width": 2.5, "dash": "dot"},
            marker={"size": 7},
            hovertemplate="<b>n = %{x} paradas</b><br>Operações (n²): %{y:,}<extra></extra>",
        )
    )

    fig.update_layout(
        title={
            "text": "Crescimento Combinatório O(n!) vs Heurística O(n²)",
            "font": {"size": 14, "color": "#0F172A"},
        },
        template="plotly_white",
        height=330,
        xaxis={"title": "Paradas (n)", "dtick": 1},
        yaxis={"title": "Operações (escala log)", "type": "log"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
            "font": {"size": 11},
        },
        margin={"l": 36, "r": 20, "t": 58, "b": 36},
    )

    return fig


def render_weather_timeline_chart(
    weather_df: pd.DataFrame,
    title: str = "Previsão Horária: Chuva e Temperatura",
) -> None:
    """Renderiza o gráfico de linha do tempo meteorológica no Streamlit."""
    st.plotly_chart(build_weather_timeline_figure(weather_df, title=title), use_container_width=True)


def render_stop_risk_chart(stops_df: pd.DataFrame) -> None:
    """Renderiza o gráfico de barras de risco climático por parada no Streamlit."""
    st.plotly_chart(build_stop_risk_bar_figure(stops_df), use_container_width=True)


def render_complexity_chart(max_n: int = 10) -> None:
    """Renderiza o gráfico de crescimento fatorial vs polinomial no Streamlit."""
    st.plotly_chart(build_complexity_comparison_figure(max_n=max_n), use_container_width=True)
