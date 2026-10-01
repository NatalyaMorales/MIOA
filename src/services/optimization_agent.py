"""
Agente de optimización de presupuesto (Budget Optimization).

Este módulo implementa los 4 modos de optimización solicitados,
reutilizando ÚNICAMENTE la función de cálculo del MMM ya existente
(calculate_expected_response, en src/models/response_curves.py).
NO se reimplementan las ecuaciones del MMM aquí.

Modos:

1. optimize_simple_shift
   Para cada medio, evalúa el ROI en el escenario base, en el
   máximo permitido de aumento y en el máximo permitido de
   disminución, y se queda con el punto de MAYOR ROI. El
   movimiento siempre es máximo (hacia arriba o hacia abajo), nunca
   parcial. Esto garantiza que el ROI optimizado (por medio y en
   total) sea siempre mayor o igual al ROI base.

2. optimize_fixed_budget
   Reasigna el presupuesto del escenario base entre medios,
   manteniendo la suma total del presupuesto, para maximizar el
   Expected Response total. Cada medio solo puede moverse dentro de
   su % permitido (de aumento / disminución) respecto al escenario
   base.

3. optimize_target
   Reasigna el presupuesto entre medios (dentro del % permitido por
   medio) para acercarse lo más posible a un ROI o Expected Response
   objetivo definido por el usuario.

4. optimize_both_ways
   Paso 1: igual que optimize_fixed_budget (mismo presupuesto total,
   mejor distribución).
   Paso 2: busca el menor presupuesto total posible (dentro del %
   permitido por medio) que aún alcance el mismo Expected Response
   logrado en el Paso 1.

Todas las funciones reciben `media_params`, un diccionario con la
forma:

    {
        "TV": {"modelo": "Modelo 1", "curve_a": ..., "curve_b": ..., "curve_c": ...},
        "OOH": {...},
        ...
    }

y dos diccionarios {medio: pct}: `pct_up_by_media` (máximo % de
aumento permitido) y `pct_down_by_media` (máximo % de disminución
permitido), ambos respecto al escenario base.
"""
from __future__ import annotations

from scipy.optimize import minimize, minimize_scalar

from src.models.marginal_return import calculate_marginal_return
from src.models.response_curves import calculate_expected_response
from src.utils.range_validation import spend_range_status


class OptimizationError(ValueError):
    """Error de negocio al ejecutar una optimización (no técnico/traceback)."""


def _response_for_media(medio: str, spend: float, media_params: dict) -> float:
    params = media_params[medio]
    return calculate_expected_response(
        spend=spend,
        model=params["modelo"],
        curve_a=params["curve_a"],
        curve_b=params["curve_b"],
        curve_c=params["curve_c"],
    )


def _marginal_for_media(medio: str, spend: float, media_params: dict) -> float:
    params = media_params[medio]
    return calculate_marginal_return(
        spend=spend,
        model=params["modelo"],
        curve_a=params["curve_a"],
        curve_b=params["curve_b"],
        curve_c=params["curve_c"],
    )


def _roi_for_media(medio: str, spend: float, media_params: dict) -> float:
    if spend <= 0:
        return 0.0
    return _response_for_media(medio, spend, media_params) / spend


def _maximize_roi_in_range(
    medio: str,
    lower: float,
    upper: float,
    media_params: dict,
    coarse_points: int = 41,
) -> tuple[float, float]:
    """
    Busca el spend que maximiza el ROI de un medio dentro de
    [lower, upper] — un rango CONTINUO, no solo los dos extremos.
    Esto permite que el movimiento óptimo sea cualquier punto entre
    0% y el % máximo permitido (por ejemplo 7%, no forzosamente 20%).

    Primero se hace un barrido en malla (coarse_points puntos) para
    ubicar la región del máximo sin asumir que el ROI es unimodal en
    todo el rango (las curvas del MMM pueden no serlo). Después se
    afina con una búsqueda acotada (Brent) alrededor del mejor punto
    de la malla, para no quedar atado a la resolución de la malla.
    """
    if upper <= lower:
        spend = max(lower, 0.0)
        return spend, _roi_for_media(medio, spend, media_params)

    step = (upper - lower) / (coarse_points - 1)
    grid = [lower + i * step for i in range(coarse_points)]
    rois = [_roi_for_media(medio, spend, media_params) for spend in grid]

    best_idx = max(range(len(grid)), key=lambda i: rois[i])
    best_spend, best_roi = grid[best_idx], rois[best_idx]

    left = grid[max(0, best_idx - 1)]
    right = grid[min(len(grid) - 1, best_idx + 1)]

    if right > left:
        refine_result = minimize_scalar(
            lambda spend: -_roi_for_media(medio, spend, media_params),
            bounds=(left, right),
            method="bounded",
            options={"xatol": 1e-6},
        )
        if refine_result.success and -refine_result.fun > best_roi:
            best_spend, best_roi = float(refine_result.x), -refine_result.fun

    return best_spend, best_roi


def _total_response(spends: list[float], medios: list[str], media_params: dict) -> float:
    return sum(
        _response_for_media(medio, spend, media_params)
        for medio, spend in zip(medios, spends)
    )


def _bounds_for_media(
    medios: list[str],
    base_spend: dict,
    pct_up_by_media: dict,
    pct_down_by_media: dict,
) -> list[tuple[float, float]]:
    bounds = []
    for medio in medios:
        base = base_spend[medio]
        pct_up = max(0.0, pct_up_by_media.get(medio, 0.0)) / 100.0
        pct_down = max(0.0, pct_down_by_media.get(medio, 0.0)) / 100.0
        lower = max(0.0, base * (1 - pct_down))
        upper = base * (1 + pct_up)
        if upper < lower:
            upper = lower
        bounds.append((lower, upper))
    return bounds


def _multi_start_minimize(
    objective,
    bounds: list[tuple[float, float]],
    x0_candidates: list[list[float]],
    constraints=None,
    constraint_scale: float = 1.0,
):
    """
    Ejecuta SLSQP desde varios puntos de partida (escenario base,
    límites inferiores, límites superiores y punto medio) y conserva
    el mejor resultado. Esto reduce el riesgo de quedar atrapado en
    un óptimo local o en un punto donde el gradiente numérico
    parece artificialmente plano, algo que puede ocurrir con las
    curvas sigmoides/potencia del MMM según la escala de sus
    parámetros.

    `constraint_scale` es la magnitud típica de las restricciones
    (por ejemplo, el presupuesto total o el Expected Response
    objetivo), usada para juzgar si una solución las cumple de forma
    numéricamente razonable sin importar su escala.
    """
    best_result = None
    tolerance = max(abs(constraint_scale) * 1e-4, 1e-6)

    # Paso de las diferencias finitas de SLSQP. El valor por defecto
    # de scipy (~1.5e-8) está pensado para variables de magnitud ~1;
    # aquí las variables son pesos (del orden de 1e5-1e7) y la
    # respuesta es del orden de 1e6, por lo que ese paso produce
    # gradientes numéricos ruidosos y el optimizador se detiene en
    # soluciones ligeramente subóptimas (los retornos marginales de
    # medios con margen de movimiento no llegaban a igualarse). Se
    # escala el paso a la magnitud típica del spend.
    typical_spend = sum(abs(v) for v in x0_candidates[0]) / max(len(x0_candidates[0]), 1)
    fd_step = max(typical_spend * 1e-6, 1e-3)

    for x0 in x0_candidates:
        try:
            result = minimize(
                objective,
                x0=x0,
                bounds=bounds,
                constraints=constraints or [],
                method="SLSQP",
                options={"maxiter": 300, "ftol": 1e-12, "eps": fd_step},
            )
        except Exception:
            continue

        violation = 0.0
        for c in constraints or []:
            value = c["fun"](result.x)
            if c["type"] == "eq":
                violation = max(violation, abs(value))
            else:  # "ineq": value should be >= 0
                violation = max(violation, max(0.0, -value))

        # Se descartan soluciones que violen de forma relevante las
        # restricciones (por ejemplo, el presupuesto total en
        # optimize_fixed_budget), incluso si su objetivo se ve mejor.
        if violation > tolerance:
            continue

        if best_result is None or result.fun < best_result.fun:
            best_result = result

    if best_result is None:
        raise OptimizationError("The optimizer could not find a solution with the given constraints.")

    return best_result


def _starting_points(bounds: list[tuple[float, float]], base_x: list[float]) -> list[list[float]]:
    lower = [b[0] for b in bounds]
    upper = [b[1] for b in bounds]
    midpoint = [(b[0] + b[1]) / 2 for b in bounds]
    return [base_x, lower, upper, midpoint]


def _build_result(media_params: dict, base_spend: dict, optimized_spend: dict) -> dict:
    """
    Arma la estructura de resultado común a todos los modos de
    optimización: detalle por medio + totales (incluyendo ROI base
    y optimizado, tanto por medio como en total).
    """
    media_rows = {}
    total_base_spend = 0.0
    total_opt_spend = 0.0
    total_base_response = 0.0
    total_opt_response = 0.0

    for medio in base_spend:
        base_s = float(base_spend[medio])
        opt_s = float(optimized_spend[medio])

        base_r = _response_for_media(medio, base_s, media_params)
        opt_r = _response_for_media(medio, opt_s, media_params)

        base_roi = (base_r / base_s) if base_s > 0 else 0.0
        opt_roi = (opt_r / opt_s) if opt_s > 0 else 0.0

        delta_pct = ((opt_s - base_s) / base_s * 100.0) if base_s > 0 else 0.0

        min_real = media_params[medio].get("min_spend_real")
        max_real = media_params[medio].get("max_spend_real")

        media_rows[medio] = {
            "base_spend": base_s,
            "optimized_spend": opt_s,
            "delta_pct": delta_pct,
            "base_response": base_r,
            "optimized_response": opt_r,
            "base_roi": base_roi,
            "optimized_roi": opt_roi,
            "base_marginal_return": _marginal_for_media(medio, base_s, media_params),
            "optimized_marginal_return": _marginal_for_media(medio, opt_s, media_params),
            "min_spend_real": min_real,
            "max_spend_real": max_real,
            "base_range_status": spend_range_status(base_s, min_real, max_real),
            "optimized_range_status": spend_range_status(opt_s, min_real, max_real),
        }

        total_base_spend += base_s
        total_opt_spend += opt_s
        total_base_response += base_r
        total_opt_response += opt_r

    totals = {
        "base_budget": total_base_spend,
        "optimized_budget": total_opt_spend,
        "base_response": total_base_response,
        "optimized_response": total_opt_response,
        "base_roi": (total_base_response / total_base_spend) if total_base_spend > 0 else 0.0,
        "optimized_roi": (total_opt_response / total_opt_spend) if total_opt_spend > 0 else 0.0,
    }

    return {"media": media_rows, "totals": totals}


def optimize_simple_shift(
    media_params: dict,
    base_spend: dict,
    pct_up_by_media: dict,
    pct_down_by_media: dict,
) -> dict:
    """
    Modo 1 — Optimización simple.

    Para cada medio se busca el spend que maximiza su ROI dentro del
    rango PERMITIDO [base*(1-pct_down), base*(1+pct_up)] — un rango
    continuo, no solo los dos extremos. El resultado puede ser
    cualquier punto entre 0% y el % máximo permitido (por ejemplo
    7% de aumento), no forzosamente el tope.

    Un candidato solo se propone para un medio si su ROI en ese
    punto óptimo es mayor al ROI base de ese medio (nunca se ofrece
    un movimiento que empeore el ROI individual; si el óptimo dentro
    del rango es el propio base, el medio simplemente no se mueve).

    Como el ROI TOTAL es un promedio ponderado por spend (no la
    suma de ROIs individuales), mejorar el ROI de un medio de forma
    aislada no garantiza matemáticamente que el ROI total mejore:
    si el spend se desplaza hacia un medio de menor ROI relativo
    (aunque ese medio mejore su PROPIO ROI), el promedio ponderado
    total puede diluirse. Por eso los movimientos candidatos se
    aplican de forma golosa (greedy), en orden del de mayor ROI
    marginal (Δresponse/Δspend) al de menor, y cada uno se acepta
    únicamente si no reduce el ROI total acumulado hasta ese punto.
    Esto garantiza que el ROI optimizado —por medio y en total—
    nunca sea menor al base, sin descartar las mejoras válidas de
    otros medios cuando alguna no aplica.
    """
    base_roi_by_media = {
        medio: _roi_for_media(medio, base, media_params) for medio, base in base_spend.items()
    }

    # 1) Se genera, por medio, el mejor candidato dentro de todo el
    #    rango permitido (no solo los extremos), y solo se conserva
    #    si mejora su propio ROI respecto al base.
    candidates_by_media: dict[str, float] = {}

    for medio, base in base_spend.items():
        pct_up = max(0.0, pct_up_by_media.get(medio, 0.0)) / 100.0
        pct_down = max(0.0, pct_down_by_media.get(medio, 0.0)) / 100.0
        base_roi = base_roi_by_media[medio]

        lower = max(0.0, base * (1 - pct_down))
        upper = base * (1 + pct_up)
        if upper <= lower:
            continue  # sin margen de movimiento (pct_up=0 y pct_down=0)

        best_spend, best_roi = _maximize_roi_in_range(medio, lower, upper, media_params)

        if best_roi > base_roi:
            candidates_by_media[medio] = best_spend

    # 2) Se aplican los candidatos de forma golosa, priorizando el
    #    de mayor ROI marginal, y solo si no reducen el ROI total
    #    acumulado hasta ese momento.
    optimized_spend = dict(base_spend)

    def marginal_roi(medio: str, candidate_spend: float) -> float:
        base = base_spend[medio]
        delta_spend = candidate_spend - base
        if delta_spend == 0:
            return float("-inf")
        base_r = _response_for_media(medio, base, media_params)
        cand_r = _response_for_media(medio, candidate_spend, media_params)
        return (cand_r - base_r) / delta_spend

    ordered_media = sorted(
        candidates_by_media.keys(),
        key=lambda medio: marginal_roi(medio, candidates_by_media[medio]),
        reverse=True,
    )

    current_total_response = sum(
        _response_for_media(medio, base_spend[medio], media_params) for medio in base_spend
    )
    current_total_spend = sum(base_spend.values())

    for medio in ordered_media:
        candidate_spend = candidates_by_media[medio]

        base_r_i = _response_for_media(medio, base_spend[medio], media_params)
        cand_r_i = _response_for_media(medio, candidate_spend, media_params)

        trial_total_response = current_total_response - base_r_i + cand_r_i
        trial_total_spend = current_total_spend - base_spend[medio] + candidate_spend

        trial_roi = (trial_total_response / trial_total_spend) if trial_total_spend > 0 else 0.0
        current_roi = (current_total_response / current_total_spend) if current_total_spend > 0 else 0.0

        if trial_roi >= current_roi:
            optimized_spend[medio] = candidate_spend
            current_total_response = trial_total_response
            current_total_spend = trial_total_spend

    return _build_result(media_params, base_spend, optimized_spend)


def optimize_fixed_budget(
    media_params: dict,
    base_spend: dict,
    pct_up_by_media: dict,
    pct_down_by_media: dict,
) -> dict:
    """
    Modo 2 — Optimización a presupuesto fijo: reasigna el
    presupuesto del escenario base entre medios (la suma se
    mantiene igual al presupuesto base) para maximizar el Expected
    Response total, respetando el % permitido (aumento/disminución)
    por medio.
    """
    medios = list(base_spend.keys())
    bounds = _bounds_for_media(medios, base_spend, pct_up_by_media, pct_down_by_media)
    total_budget = sum(base_spend.values())

    lower_sum = sum(b[0] for b in bounds)
    upper_sum = sum(b[1] for b in bounds)
    if not (lower_sum <= total_budget <= upper_sum):
        raise OptimizationError(
            "The allowed % per Media does not leave enough room to "
            "reallocate the same total budget. Increase the allowed % "
            "for one or more Media and try again."
        )

    x0 = [base_spend[m] for m in medios]

    def objective(x):
        return -_total_response(x, medios, media_params)

    constraints = [{"type": "eq", "fun": lambda x: sum(x) - total_budget}]

    result = _multi_start_minimize(
        objective,
        bounds=bounds,
        x0_candidates=_starting_points(bounds, x0),
        constraints=constraints,
        constraint_scale=total_budget,
    )

    optimized_spend = dict(zip(medios, result.x.tolist()))
    return _build_result(media_params, base_spend, optimized_spend)


def optimize_target(
    media_params: dict,
    base_spend: dict,
    pct_up_by_media: dict,
    pct_down_by_media: dict,
    target_value: float,
    target_metric: str = "response",
) -> dict:
    """
    Modo 3 — Optimización hacia un ROI/Response objetivo: reasigna
    el presupuesto entre medios (dentro del % permitido por medio)
    para acercarse lo más posible a `target_value`, medido en
    `target_metric` ("response" o "roi").
    """
    if target_metric not in {"response", "roi"}:
        raise OptimizationError(f"Unsupported target metric: {target_metric}")

    medios = list(base_spend.keys())
    bounds = _bounds_for_media(medios, base_spend, pct_up_by_media, pct_down_by_media)
    x0 = [base_spend[m] for m in medios]

    def objective(x):
        total_response = _total_response(x, medios, media_params)
        if target_metric == "response":
            current = total_response
        else:
            total_spend = sum(x)
            current = (total_response / total_spend) if total_spend > 0 else 0.0
        return (current - target_value) ** 2

    result = _multi_start_minimize(
        objective,
        bounds=bounds,
        x0_candidates=_starting_points(bounds, x0),
    )

    optimized_spend = dict(zip(medios, result.x.tolist()))
    return _build_result(media_params, base_spend, optimized_spend)


def optimize_both_ways(
    media_params: dict,
    base_spend: dict,
    pct_up_by_media: dict,
    pct_down_by_media: dict,
) -> dict:
    """
    Modo 4 — Optimización both-ways:

    Paso 1: igual que optimize_fixed_budget (mismo presupuesto
    total, mejor distribución -> maximiza Expected Response).

    Paso 2: busca el menor presupuesto total (dentro del % permitido
    por medio) que aún alcance el Expected Response logrado en el
    Paso 1.
    """
    step_1 = optimize_fixed_budget(media_params, base_spend, pct_up_by_media, pct_down_by_media)
    target_response = step_1["totals"]["optimized_response"]

    medios = list(base_spend.keys())
    bounds = _bounds_for_media(medios, base_spend, pct_up_by_media, pct_down_by_media)
    x0 = [base_spend[m] for m in medios]

    # Verifica que sea alcanzable con el máximo presupuesto permitido
    max_achievable_response = _total_response([b[1] for b in bounds], medios, media_params)
    feasibility_tolerance = max(abs(target_response) * 1e-4, 1e-6)
    if max_achievable_response < target_response - feasibility_tolerance:
        raise OptimizationError(
            "The allowed % per Media does not leave enough room to reach "
            "the Step 1 Expected Response with a smaller budget. Increase "
            "the allowed % for one or more Media and try again."
        )

    def total_spend(x):
        return sum(x)

    def response_constraint(x):
        return _total_response(x, medios, media_params) - target_response

    constraints = [{"type": "ineq", "fun": response_constraint}]

    result = _multi_start_minimize(
        total_spend,
        bounds=bounds,
        x0_candidates=_starting_points(bounds, x0),
        constraints=constraints,
        constraint_scale=target_response,
    )

    optimized_spend = dict(zip(medios, result.x.tolist()))
    step_2 = _build_result(media_params, base_spend, optimized_spend)

    return {"fixed_budget_step": step_1, "budget_minimization_step": step_2}


def optimize_total_budget(
    media_params: dict,
    total_budget: float,
    media_list: list[str],
    min_spend_by_media: dict | None = None,
    max_spend_by_media: dict | None = None,
) -> dict:
    """
    Optimización de Presupuesto Total (Total Budget Optimization).

    A diferencia de los 4 modos anteriores, aquí NO existe un
    escenario base: el usuario solo define un presupuesto total y
    los medios entre los que quiere repartirlo. La función busca la
    asignación que maximiza el Expected Response total, sujeta a que
    la suma asignada sea exactamente `total_budget`.

    Opcionalmente se pueden imponer mínimos y máximos de inversión
    por medio (`min_spend_by_media` / `max_spend_by_media`), por
    ejemplo para respetar mínimos de compra de un medio o topes de
    capacidad. Si no se indican, el rango por medio es
    [0, total_budget].

    Reutiliza calculate_expected_response() del motor MMM existente;
    no reimplementa ecuaciones.

    Returns
    -------
    dict con la misma forma que _build_result(), donde el
    "escenario base" es una distribución equitativa del presupuesto
    entre los medios seleccionados (referencia neutral para
    comparar), y el "optimizado" es la asignación óptima.
    """
    if not media_list:
        raise OptimizationError("Select at least one Media to allocate the budget.")

    if total_budget <= 0:
        raise OptimizationError("Total Budget must be greater than 0.")

    min_spend_by_media = min_spend_by_media or {}
    max_spend_by_media = max_spend_by_media or {}

    bounds = []
    for medio in media_list:
        lower = max(0.0, float(min_spend_by_media.get(medio, 0.0)))
        upper = float(max_spend_by_media.get(medio, total_budget))
        if upper < lower:
            upper = lower
        bounds.append((lower, upper))

    lower_sum = sum(b[0] for b in bounds)
    upper_sum = sum(b[1] for b in bounds)

    if lower_sum > total_budget:
        raise OptimizationError(
            "The sum of the minimum spends per Media exceeds the Total "
            "Budget. Lower the minimums or increase the Total Budget."
        )
    if upper_sum < total_budget:
        raise OptimizationError(
            "The sum of the maximum spends per Media is lower than the "
            "Total Budget. Raise the maximums or lower the Total Budget."
        )

    def objective(x):
        return -_total_response(x, media_list, media_params)

    constraints = [{"type": "eq", "fun": lambda x: sum(x) - total_budget}]

    # Punto de partida neutral: reparto equitativo, ajustado a los
    # límites por medio. Se complementa con los puntos de partida
    # estándar (límites y punto medio) para el multi-start.
    equal_share = [total_budget / len(media_list)] * len(media_list)
    equal_share = [
        min(max(value, bound[0]), bound[1]) for value, bound in zip(equal_share, bounds)
    ]

    result = _multi_start_minimize(
        objective,
        bounds=bounds,
        x0_candidates=_starting_points(bounds, equal_share),
        constraints=constraints,
        constraint_scale=total_budget,
    )

    optimized_spend = dict(zip(media_list, result.x.tolist()))

    # Referencia de comparación: reparto equitativo del presupuesto.
    reference_spend = dict(zip(media_list, equal_share))

    return _build_result(media_params, reference_spend, optimized_spend)

