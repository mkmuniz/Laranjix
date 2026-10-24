"""T2 - golpes de engenharia social.

Falsa central de atendimento, golpe do WhatsApp, falso sequestro, golpe da
devolucao. O que esses golpes tem em comum nao e o roteiro, e a forma do
dinheiro: varias vitimas sem relacao entre si pagam a mesma conta em uma janela
curta, e o valor sai logo em seguida.

**Assinatura no grafo, do ponto de vista de quem detecta:** fan-in de pagadores
que nunca transacionaram com aquele recebedor nem entre si, concentrado no
tempo, seguido de fan-out rapido. A ausencia de historico entre as partes e o
sinal mais forte -- e por isso que a movimentacao normal precisa ter um circulo
de contrapartes recorrentes, senao "par novo" nao distingue nada.

Fonte: comunicados do BCB e das instituicoes sobre golpes do Pix; Carta Circular
BCB no 4.001/2020.
"""

from __future__ import annotations

import numpy as np

from laranjix.typologies.base import Case, InjectionContext, InjectionResult, PlantedTransaction

CODE = "T2"
NAME = "Golpes de engenharia social"
SOURCE = "Comunicados oficiais do BCB sobre golpes do Pix; Carta Circular BCB 4.001/2020"


def _victim_amount(context: InjectionContext, victim: str) -> float:
    if context.rng.random() < context.difficulty.amount_from_history:
        base = context.typical_amount(victim, fallback=600.0)
        return float(np.clip(base * context.rng.uniform(0.8, 2.0), 40.0, 20_000.0))
    return float(context.rng.choice([300, 500, 800, 1_000, 1_500, 2_500]))


def inject(context: InjectionContext) -> InjectionResult:
    """Plant the configured number of social-engineering cases."""
    rng = context.rng
    settings = context.difficulty
    fraud = context.fraud
    transactions: list[PlantedTransaction] = []
    cases: list[Case] = []

    if fraud.social_engineering_cases <= 0 or context.normal.height == 0:
        return InjectionResult()

    individuals = context.accounts.filter(context.accounts["holder_type"] == "PF")[
        "account_id"
    ].to_numpy()
    everyone = context.accounts["account_id"].to_numpy()
    with_history = context.active_accounts()
    if individuals.size < 2:
        return InjectionResult()

    timestamps = context.normal["timestamp"].to_numpy()
    first, last = timestamps.min(), timestamps.max()
    span_seconds = max(int((last - first) / np.timedelta64(1, "s")), 1)

    for index in range(fraud.social_engineering_cases):
        case_id = f"case_{CODE}_{index + 1:05d}"
        victim_count = int(rng.integers(fraud.victims_per_case_min, fraud.victims_per_case_max + 1))
        victims = rng.choice(individuals, size=victim_count, replace=False)

        pool = (
            with_history
            if with_history.size and rng.random() < settings.mule_history_fraction
            else everyone
        )
        collector = str(rng.choice(pool))
        roles: dict[str, str] = {collector: "collector"}

        start_offset = int(rng.integers(0, span_seconds))
        window_start = first + np.timedelta64(start_offset, "s")
        # Victims pay within a window; the harder the level, the wider it is.
        window_seconds = int(settings.hop_minutes_max * 60 * 4)

        total = 0.0
        last_payment = window_start
        for victim in victims:
            victim_id = str(victim)
            if victim_id == collector:
                continue
            roles[victim_id] = "victim"
            moment = window_start + np.timedelta64(int(rng.integers(0, window_seconds)), "s")
            amount = _victim_amount(context, victim_id)
            transactions.append(
                PlantedTransaction(
                    src_account_id=victim_id,
                    dst_account_id=collector,
                    amount=round(amount, 2),
                    timestamp=moment,
                    channel="pix",
                    device_id=f"dev_{victim_id.removeprefix('acc_').lstrip('0') or '0'}",
                    case_id=case_id,
                    typology=CODE,
                    role="victim_payment",
                )
            )
            total += amount
            last_payment = max(last_payment, moment)

        # The collector pushes the money out fast, in a handful of slices.
        slices = int(rng.integers(2, 5))
        remaining = total * rng.uniform(
            settings.retained_fraction_min, settings.retained_fraction_max
        )
        onward_targets = rng.choice(everyone, size=slices)
        moment = last_payment
        for position, target in enumerate(onward_targets, start=1):
            target_id = str(target)
            if target_id == collector:
                continue
            roles.setdefault(target_id, "cash_out")
            share = remaining / slices
            gap = rng.uniform(settings.hop_minutes_min, settings.hop_minutes_max)
            moment = moment + np.timedelta64(int(gap * 60), "s")
            transactions.append(
                PlantedTransaction(
                    src_account_id=collector,
                    dst_account_id=target_id,
                    amount=round(max(share, 1.0), 2),
                    timestamp=moment,
                    channel="pix",
                    device_id=f"dev_{collector.removeprefix('acc_').lstrip('0') or '0'}",
                    case_id=case_id,
                    typology=CODE,
                    role=f"fan_out_{position}",
                )
            )

        cases.append(
            Case(
                case_id=case_id,
                typology=CODE,
                difficulty=context.difficulty_name,
                start_ts=window_start,
                end_ts=moment,
                depth=2,
                total_amount=round(total, 2),
                accounts=roles,
                source_reference=SOURCE,
            )
        )
    return InjectionResult(transactions=transactions, cases=cases)
