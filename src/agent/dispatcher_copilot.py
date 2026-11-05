"""Copiloto agêntico de despacho logístico para análise de risco climático e otimização de rotas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.domain.delivery import DeliveryStop, RoutePlan
from src.domain.weather import ClimateRiskLevel
from src.mathematics.permutations import calculate_factorial, estimate_brute_force_time_ms
from src.mathematics.risk_matrix import evaluate_stops_risk
from src.mathematics.routing import build_optimized_route, calculate_route_distance


class DispatchAlertSeverity(str, Enum):
    """Severidade das recomendações emitidas pelo Copiloto de Despacho."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DispatchRecommendation(BaseModel):
    """Recomendação tática ou alerta operacional gerado pelo Copiloto de Despacho."""

    stop_id: str | None = Field(
        default=None, description="ID da parada associada à recomendação (se aplicável)"
    )
    severity: DispatchAlertSeverity = Field(
        ..., description="Grau de severidade do alerta operacional"
    )
    title: str = Field(..., description="Título curto da recomendação")
    message: str = Field(..., description="Explicação detalhada do diagnóstico")
    suggested_action: str = Field(..., description="Ação prática recomendada ao despachante")


class CopilotAnalysisReport(BaseModel):
    """Relatório consolidado da análise agêntica de roteirização e risco meteorológico."""

    route_plan: RoutePlan = Field(..., description="Plano de rota otimizado pelo motor matemático")
    baseline_distance_km: float = Field(
        default=0.0, ge=0.0, description="Distância total na ordem original sem otimização (km)"
    )
    distance_saved_km: float = Field(
        default=0.0, ge=0.0, description="Quilometragem economizada pela otimização (km)"
    )
    critical_stops_count: int = Field(
        default=0, ge=0, description="Total de paradas com risco climático CRÍTICO"
    )
    high_risk_stops_count: int = Field(
        default=0, ge=0, description="Total de paradas com risco climático ALTO"
    )
    best_weather_window: str = Field(
        default="09:00 - 12:00", description="Melhor janela contínua de 3 horas para operação"
    )
    recommendations: list[DispatchRecommendation] = Field(
        default_factory=list, description="Lista priorizada de recomendações e alertas táticos"
    )
    executive_summary: str = Field(
        ..., description="Resumo executivo em linguagem natural para tomada de decisão"
    )


class DispatcherCopilot:
    """Agente especialista de apoio à decisão para expedição urbana sob incerteza climática."""

    def analyze_and_optimize(
        self,
        origin: DeliveryStop,
        stops: list[DeliveryStop],
        alpha: float = 0.5,
    ) -> CopilotAnalysisReport:
        """Avalia riscos climáticos, otimiza a sequência de entregas e gera recomendações táticas.

        Args:
            origin: Ponto de partida (Centro de Distribuição).
            stops: Lista de paradas de entrega planejadas.
            alpha: Peso de penalização climática na função objetivo de roteirização.

        Returns:
            Instância de `CopilotAnalysisReport` com plano otimizado, métricas e alertas.
        """
        evaluated_stops = evaluate_stops_risk(stops)
        baseline_distance_km = calculate_route_distance(origin, evaluated_stops)
        route_plan = build_optimized_route(origin, evaluated_stops, alpha=alpha, use_2opt=True)
        distance_saved_km = round(
            max(0.0, baseline_distance_km - route_plan.total_distance_km), 4
        )

        best_window = self._find_best_weather_window(route_plan.ordered_stops)

        critical_stops = [
            s for s in route_plan.ordered_stops if s.risk_level == ClimateRiskLevel.CRITICO
        ]
        high_risk_stops = [
            s for s in route_plan.ordered_stops if s.risk_level == ClimateRiskLevel.ALTO
        ]

        recommendations = self._generate_recommendations(
            route_plan=route_plan,
            baseline_distance_km=baseline_distance_km,
            distance_saved_km=distance_saved_km,
        )

        executive_summary = self._build_executive_summary(
            route_plan=route_plan,
            baseline_distance_km=baseline_distance_km,
            distance_saved_km=distance_saved_km,
            critical_count=len(critical_stops),
            high_risk_count=len(high_risk_stops),
            best_window=best_window,
        )

        return CopilotAnalysisReport(
            route_plan=route_plan,
            baseline_distance_km=baseline_distance_km,
            distance_saved_km=distance_saved_km,
            critical_stops_count=len(critical_stops),
            high_risk_stops_count=len(high_risk_stops),
            best_weather_window=best_window,
            recommendations=recommendations,
            executive_summary=executive_summary,
        )

    @staticmethod
    def _find_best_weather_window(stops: list[DeliveryStop]) -> str:
        """Identifica a janela de 3 horas consecutivas (entre 08h e 18h) com menor severidade climática."""
        forecasts = [s.weather_forecast for s in stops if s.weather_forecast is not None]
        if not forecasts:
            return "09:00 - 12:00"

        best_start_hour = 9
        best_score = float("inf")
        found_any_points = False

        for start_hour in range(8, 16):
            window_hours = (start_hour, start_hour + 1, start_hour + 2)
            penalties: list[float] = []
            for forecast in forecasts:
                for h in window_hours:
                    pt = forecast.get_point_for_hour(h)
                    if pt is not None:
                        found_any_points = True
                        penalty = (
                            pt.precipitation_mm * 2.5
                            + (pt.precipitation_probability / 100.0) * 5.0
                            + (pt.wind_speed_kmh / 50.0) * 2.5
                        )
                        penalties.append(penalty)

            if penalties:
                avg_penalty = sum(penalties) / len(penalties)
                if avg_penalty < best_score:
                    best_score = avg_penalty
                    best_start_hour = start_hour

        if not found_any_points:
            return "09:00 - 12:00"

        return f"{best_start_hour:02d}:00 - {best_start_hour + 3:02d}:00"

    @staticmethod
    def _generate_recommendations(
        route_plan: RoutePlan,
        baseline_distance_km: float,
        distance_saved_km: float,
    ) -> list[DispatchRecommendation]:
        """Constrói recomendações estruturadas com base nos níveis de risco e na otimização."""
        recommendations: list[DispatchRecommendation] = []

        for stop in route_plan.ordered_stops:
            max_rain = (
                stop.weather_forecast.max_precipitation_mm()
                if stop.weather_forecast is not None
                else 0.0
            )
            max_wind = (
                stop.weather_forecast.max_wind_speed_kmh()
                if stop.weather_forecast is not None
                else 0.0
            )

            if stop.risk_level == ClimateRiskLevel.CRITICO:
                recommendations.append(
                    DispatchRecommendation(
                        stop_id=stop.id,
                        severity=DispatchAlertSeverity.CRITICAL,
                        title=(
                            f"Alerta Crítico de Intempérie: {stop.recipient_name} "
                            f"({stop.address.bairro})"
                        ),
                        message=(
                            f"Condição severa prevista para o CEP {stop.address.cep} "
                            f"({stop.address.bairro}) com chuva máxima de {max_rain:.1f} mm/h, "
                            f"ventos de {max_wind:.1f} km/h e score de risco {stop.risk_score:.2f}."
                        ),
                        suggested_action=(
                            "Antecipar janela de entrega para horário de estiagem ou aplicar "
                            "embalagem impermeável reforçada e confirmar recebimento imediato."
                        ),
                    )
                )
            elif stop.risk_level == ClimateRiskLevel.ALTO:
                recommendations.append(
                    DispatchRecommendation(
                        stop_id=stop.id,
                        severity=DispatchAlertSeverity.WARNING,
                        title=(
                            f"Atenção Climática: {stop.recipient_name} ({stop.address.bairro})"
                        ),
                        message=(
                            f"Risco climático alto no CEP {stop.address.cep} "
                            f"({stop.address.bairro}) com precipitação de até {max_rain:.1f} mm/h, "
                            f"ventos de {max_wind:.1f} km/h e score {stop.risk_score:.2f}."
                        ),
                        suggested_action=(
                            "Priorizar parada na sequência da rota e manter atenção redobrada "
                            "a lentidão e alagamentos pontuais no trânsito."
                        ),
                    )
                )

        n_stops = len(route_plan.ordered_stops)
        total_perms = calculate_factorial(n_stops)
        brute_force_ms = estimate_brute_force_time_ms(n_stops)
        pct_saved = (
            (distance_saved_km / baseline_distance_km * 100.0)
            if baseline_distance_km > 0.0
            else 0.0
        )

        recommendations.append(
            DispatchRecommendation(
                stop_id=None,
                severity=DispatchAlertSeverity.INFO,
                title="Desempenho da Otimização Combinatória (2-Opt + Risco)",
                message=(
                    f"Espaço de busca de {n_stops}! = {total_perms:,} permutações "
                    f"(força bruta estimada em {brute_force_ms:.3f} ms) resolvido em "
                    f"{route_plan.computation_time_ms:.2f} ms pelo algoritmo "
                    f"'{route_plan.algorithm_used}'. Economia de {distance_saved_km:.2f} km "
                    f"({pct_saved:.1f}%) frente à sequência original."
                ),
                suggested_action=(
                    "Seguir a ordem otimizada de despacho para minimizar quilometragem "
                    "e exposição das cargas às janelas de chuva."
                ),
            )
        )

        return recommendations

    @staticmethod
    def _build_executive_summary(
        route_plan: RoutePlan,
        baseline_distance_km: float,
        distance_saved_km: float,
        critical_count: int,
        high_risk_count: int,
        best_window: str,
    ) -> str:
        """Gera um resumo executivo consolidado em português para o painel operacional."""
        total_stops = len(route_plan.ordered_stops)
        if total_stops == 0:
            return (
                "Nenhuma parada de entrega cadastrada para análise. "
                "Adicione paradas ao roteiro para executar o Copiloto de Despacho."
            )

        pct_saved = (
            (distance_saved_km / baseline_distance_km * 100.0)
            if baseline_distance_km > 0.0
            else 0.0
        )

        return (
            f"Roteiro analisado com {total_stops} parada(s) partindo de "
            f"{route_plan.origin.address.bairro}. A distância total otimizada é de "
            f"{route_plan.total_distance_km:.2f} km (economia de {distance_saved_km:.2f} km / "
            f"{pct_saved:.1f}% em relação à rota base de {baseline_distance_km:.2f} km). "
            f"Foram identificadas {critical_count} parada(s) em risco CRÍTICO e "
            f"{high_risk_count} em risco ALTO (score médio da rota: "
            f"{route_plan.average_risk_score:.2f}). Melhor janela operacional recomendada: "
            f"{best_window}."
        )
