"""Testes unitários para a camada de Matemática Computacional Aplicada (src/mathematics/)."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.domain import (
    Address,
    ClimateRiskLevel,
    Coordinates,
    DeliveryPriority,
    DeliveryStop,
    HourlyWeatherPoint,
    WeatherForecast,
)
from src.mathematics import (
    build_optimized_route,
    calculate_factorial,
    calculate_route_distance,
    calculate_weighted_edge_cost,
    compute_stop_risk_score,
    estimate_brute_force_time_ms,
    evaluate_stops_risk,
    generate_complexity_comparison_table,
    optimize_route_nearest_neighbor,
    parse_delivery_window_hours,
    refine_route_2opt,
    solve_tsp_brute_force,
)


def _make_stop(
    stop_id: str,
    lat: float,
    lon: float,
    priority: DeliveryPriority = DeliveryPriority.MEDIA,
    window: str = "09:00 - 18:00",
    forecast: WeatherForecast | None = None,
    risk_score: float = 0.0,
) -> DeliveryStop:
    """Helper de criação rápida de DeliveryStop com coordenadas para testes."""
    address = Address(
        cep="80020-010",
        logradouro=f"Rua {stop_id}",
        bairro="Centro",
        cidade="Curitiba",
        uf="PR",
        coordinates=Coordinates(latitude=lat, longitude=lon),
    )
    return DeliveryStop(
        id=stop_id,
        recipient_name=f"Cliente {stop_id}",
        address=address,
        priority=priority,
        delivery_window=window,
        weather_forecast=forecast,
        risk_score=risk_score,
    )


class TestPermutationsAndCombinatorics:
    """Testes para permutação simples (n!), tabela de complexidade e força bruta exata."""

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            (0, 1),
            (1, 1),
            (4, 24),
            (5, 120),
            (8, 40320),
            (10, 3628800),
            (12, 479001600),
        ],
    )
    def test_calculate_factorial_values(self, n: int, expected: int) -> None:
        assert calculate_factorial(n) == expected

    def test_calculate_factorial_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="não-negativo"):
            calculate_factorial(-1)

    def test_estimate_brute_force_time_ms(self) -> None:
        # 1500! ops/ms -> para n=6 (720 perms) = 720 / 1500 = 0.48 ms
        assert estimate_brute_force_time_ms(6, ops_per_ms=1500.0) == 0.48
        # Crescimento monotônico estrito para n >= 1
        assert estimate_brute_force_time_ms(8) > estimate_brute_force_time_ms(4)

    def test_estimate_brute_force_invalid_ops_raises(self) -> None:
        with pytest.raises(ValueError, match="positiva"):
            estimate_brute_force_time_ms(5, ops_per_ms=0.0)

    def test_generate_complexity_comparison_table(self) -> None:
        table = generate_complexity_comparison_table(max_n=10)
        assert len(table) == 10
        first = table[0]
        assert first["n"] == 1
        assert first["permutacoes_fatorial"] == 1
        assert first["operacoes_heuristica_n2"] == 1

        tenth = table[9]
        assert tenth["n"] == 10
        assert tenth["permutacoes_fatorial"] == 3628800
        assert tenth["operacoes_heuristica_n2"] == 100
        assert int(tenth["permutacoes_fatorial"]) > int(tenth["operacoes_heuristica_n2"])

    def test_generate_complexity_comparison_table_invalid_max_n(self) -> None:
        with pytest.raises(ValueError, match="pelo menos 1"):
            generate_complexity_comparison_table(max_n=0)

    def test_solve_tsp_brute_force_exceeds_limit_raises(self) -> None:
        origin = _make_stop("ORIGEM", -25.4284, -49.2733)
        stops = [_make_stop(f"S{i}", -25.43 - i * 0.01, -49.27) for i in range(9)]
        with pytest.raises(ValueError, match="limitada a 8 paradas"):
            solve_tsp_brute_force(origin, stops)

    def test_solve_tsp_brute_force_empty_stops(self) -> None:
        origin = _make_stop("ORIGEM", -25.4284, -49.2733)
        plan = solve_tsp_brute_force(origin, [])
        assert plan.ordered_stops == []
        assert plan.total_distance_km == 0.0
        assert plan.total_permutations_possible == 1
        assert plan.algorithm_used == "brute_force_exact"


class TestRiskMatrix:
    """Testes para janela de entrega, cálculo de risco climático e custo de aresta ponderado."""

    @pytest.mark.parametrize(
        ("window_str", "expected_hours"),
        [
            ("09:00 - 12:00", (9, 12)),
            ("08:00-14:00", (8, 14)),
            ("13:00 às 17:00", (13, 17)),
            ("invalido", (9, 18)),
            ("20:00 - 08:00", (9, 18)),
            ("25:00 - 27:00", (9, 18)),
        ],
    )
    def test_parse_delivery_window_hours(
        self, window_str: str, expected_hours: tuple[int, int]
    ) -> None:
        assert parse_delivery_window_hours(window_str) == expected_hours

    def test_compute_stop_risk_score_without_weather(self) -> None:
        stop_low = _make_stop("S1", -25.42, -49.27, priority=DeliveryPriority.BAIXA)
        score_low, level_low = compute_stop_risk_score(stop_low)
        # Apenas componente de prioridade: 0.20 * 0.2 = 0.04
        assert score_low == 0.04
        assert level_low == ClimateRiskLevel.BAIXO

        stop_high = _make_stop("S2", -25.42, -49.27, priority=DeliveryPriority.ALTA)
        score_high, level_high = compute_stop_risk_score(stop_high)
        # 0.20 * 1.0 = 0.20
        assert score_high == 0.20
        assert level_high == ClimateRiskLevel.BAIXO

    def test_compute_stop_risk_score_weather_scenarios(self) -> None:
        coords = Coordinates(latitude=-25.4284, longitude=-49.2733)

        # Cenário 1: Tempo seco na manhã (10h), tempestade severa à tarde (15h)
        morning_calm = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 10, 0),
            temperature_c=22.0,
            precipitation_probability=10.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
        )
        afternoon_storm = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 15, 0),
            temperature_c=17.0,
            precipitation_probability=95.0,
            precipitation_mm=18.0,
            wind_speed_kmh=55.0,
        )
        forecast = WeatherForecast(coordinates=coords, hourly=[morning_calm, afternoon_storm])

        # Parada com janela matutina (09:00 - 12:00) deve filtrar apenas a manhã calma
        morning_stop = _make_stop(
            "MANHA",
            -25.4284,
            -49.2733,
            priority=DeliveryPriority.MEDIA,
            window="09:00 - 12:00",
            forecast=forecast,
        )
        m_score, m_level = compute_stop_risk_score(morning_stop)
        assert m_score < 0.25
        assert m_level == ClimateRiskLevel.BAIXO

        # Parada com janela vespertina (14:00 - 17:00) pega a tempestade crítica
        afternoon_stop = _make_stop(
            "TARDE",
            -25.4284,
            -49.2733,
            priority=DeliveryPriority.ALTA,
            window="14:00 - 17:00",
            forecast=forecast,
        )
        a_score, a_level = compute_stop_risk_score(afternoon_stop)
        assert a_score == 1.0
        assert a_level == ClimateRiskLevel.CRITICO

    def test_evaluate_stops_risk_immutability(self) -> None:
        coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
        moderate_point = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 11, 0),
            temperature_c=20.0,
            precipitation_probability=60.0,
            precipitation_mm=4.5,
            wind_speed_kmh=25.0,
        )
        forecast = WeatherForecast(coordinates=coords, hourly=[moderate_point])
        original = _make_stop(
            "S1",
            -25.4284,
            -49.2733,
            priority=DeliveryPriority.ALTA,
            forecast=forecast,
        )

        evaluated = evaluate_stops_risk([original])
        assert len(evaluated) == 1
        assert original.risk_score == 0.0  # Imutável
        assert evaluated[0].risk_score > 0.40
        assert evaluated[0].risk_level in (ClimateRiskLevel.MODERADO, ClimateRiskLevel.ALTO)

    def test_calculate_weighted_edge_cost(self) -> None:
        stop_a = _make_stop("A", -25.4284, -49.2733, risk_score=0.0)
        stop_b_safe = _make_stop("B_SAFE", -25.4429, -49.2385, risk_score=0.0)
        stop_b_risky = _make_stop("B_RISKY", -25.4429, -49.2385, risk_score=1.0)

        base_cost = calculate_weighted_edge_cost(stop_a, stop_b_safe, alpha=0.5)
        risky_cost = calculate_weighted_edge_cost(stop_a, stop_b_risky, alpha=0.5)

        assert base_cost > 0.0
        assert risky_cost == pytest.approx(base_cost * 1.5, rel=1e-3)

    def test_calculate_weighted_edge_cost_missing_coordinates(self) -> None:
        addr_no_coords = Address(
            cep="80020-010",
            logradouro="Sem Coord",
            bairro="Centro",
            cidade="Curitiba",
            uf="PR",
            coordinates=None,
        )
        stop_no_coords = DeliveryStop(
            id="NO_COORD",
            recipient_name="Cliente",
            address=addr_no_coords,
        )
        stop_ok = _make_stop("OK", -25.4284, -49.2733)
        assert calculate_weighted_edge_cost(stop_no_coords, stop_ok) == 0.0


class TestRoutingAndOptimization:
    """Testes comparando Força Bruta, Nearest Neighbor e refinamento 2-Opt."""

    def test_2opt_uncrosses_intersecting_route(self) -> None:
        # Quadrado geométrico com cruzamento em "X" se visitado na ordem:
        # Origem (0,0) -> Top-Right -> Bottom-Left -> Top-Left -> Bottom-Right
        origin = _make_stop("ORIGEM", -25.40, -49.30)
        top_left = _make_stop("TL", -25.35, -49.30)
        top_right = _make_stop("TR", -25.35, -49.20)
        bottom_left = _make_stop("BL", -25.40, -49.25)
        bottom_right = _make_stop("BR", -25.40, -49.20)

        crossed_sequence = [top_right, bottom_left, top_left, bottom_right]
        crossed_distance = calculate_route_distance(origin, crossed_sequence)

        refined_sequence = refine_route_2opt(origin, crossed_sequence, alpha=0.0)
        refined_distance = calculate_route_distance(origin, refined_sequence)

        assert refined_distance < crossed_distance

    def test_nearest_neighbor_and_2opt_match_or_approche_brute_force(self) -> None:
        # 5 pontos reais na região de Curitiba
        origin = _make_stop("CD", -25.4284, -49.2733)  # Centro
        stops = [
            _make_stop("S1_BATEL", -25.4422, -49.2908),
            _make_stop("S2_PORTAO", -25.4761, -49.2923),
            _make_stop("S3_JARDIM_BOTANICO", -25.4429, -49.2385),
            _make_stop("S4_CABRAL", -25.4063, -49.2524),
            _make_stop("S5_MERCÊS", -25.4195, -49.2895),
        ]

        # Ordem deliberadamente embaralhada (zigue-zague norte-sul-leste-oeste)
        scrambled_distance = calculate_route_distance(origin, stops)

        exact_plan = solve_tsp_brute_force(origin, stops, alpha=0.5)
        heuristic_plan = build_optimized_route(origin, stops, alpha=0.5, use_2opt=True)

        assert heuristic_plan.total_permutations_possible == 120
        assert exact_plan.total_permutations_possible == 120
        assert heuristic_plan.algorithm_used == "nearest_neighbor_2opt"

        # A rota heurística deve ser significativamente menor ou igual à rota embaralhada
        assert heuristic_plan.total_distance_km <= scrambled_distance
        # Para 5 pontos convexos/urbanos, 2-Opt atinge ótimo exato ou muito próximo (< 5% gap)
        assert heuristic_plan.total_distance_km == pytest.approx(
            exact_plan.total_distance_km, rel=0.05
        )

    def test_risk_penalty_alpha_influences_selection(self) -> None:
        # Duas paradas equidistantes da origem, mas uma com risco crítico e outra sem risco
        origin = _make_stop("ORIGEM", -25.4000, -49.2500)

        coords_storm = Coordinates(latitude=-25.3900, longitude=-49.2500)
        storm_point = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 10, 0),
            temperature_c=16.0,
            precipitation_probability=100.0,
            precipitation_mm=25.0,
            wind_speed_kmh=60.0,
        )
        storm_forecast = WeatherForecast(coordinates=coords_storm, hourly=[storm_point])

        stop_north_storm = _make_stop(
            "NORTE_TEMPESTADE",
            -25.3900,
            -49.2500,
            priority=DeliveryPriority.ALTA,
            forecast=storm_forecast,
        )
        stop_south_clear = _make_stop(
            "SUL_LIMPO",
            -25.4100,
            -49.2500,
            priority=DeliveryPriority.BAIXA,
            forecast=None,
        )

        # Sem refinamento 2-Opt para observar diretamente a decisão gulosa do 1º passo
        plan = build_optimized_route(
            origin,
            [stop_north_storm, stop_south_clear],
            alpha=0.8,
            use_2opt=False,
        )
        assert plan.ordered_stops[0].id == "SUL_LIMPO"
        assert plan.ordered_stops[1].id == "NORTE_TEMPESTADE"
        assert plan.ordered_stops[1].risk_level == ClimateRiskLevel.CRITICO

    def test_optimize_route_nearest_neighbor_empty_and_direct(self) -> None:
        origin = _make_stop("ORIGEM", -25.4284, -49.2733)
        assert optimize_route_nearest_neighbor(origin, []) == []

        near_stop = _make_stop("PERTO", -25.4300, -49.2733)
        far_stop = _make_stop("LONGE", -25.5000, -49.2733)
        ordered = optimize_route_nearest_neighbor(origin, [far_stop, near_stop], alpha=0.0)
        assert [s.id for s in ordered] == ["PERTO", "LONGE"]

