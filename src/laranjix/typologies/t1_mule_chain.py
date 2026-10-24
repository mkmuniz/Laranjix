"""T1 - cadeia de contas laranja.

O dinheiro sai da vitima e atravessa varias contas em sequencia, em minutos ou
poucas horas, ate uma conta de saque. Cada elo retem uma fracao pequena.

**Assinatura no grafo, do ponto de vista de quem detecta:** um caminho
direcionado de 2 a 6 ou mais saltos em que o valor quase nao muda, os intervalos
entre saltos sao curtos, e o saldo nao permanece nas contas intermediarias --
entra e sai. A profundidade configuravel existe para testar o limite de cinco
camadas do rastreamento do MED 2.0.

Fonte: Resolucao BCB no 493/2025 (MED 2.0) e Carta Circular BCB no 4.001/2020.
"""

from __future__ import annotations

import numpy as np

from laranjix.typologies.base import Case, InjectionContext, InjectionResult, PlantedTransaction

CODE = "T1"
NAME = "Cadeia de contas laranja (Pix)"
SOURCE = "Resolucao BCB 493/2025 (MED 2.0); Carta Circular BCB 4.001/2020"


def _pick_mules(context: InjectionContext, count: int) -> np.ndarray:
    """Recruit mule accounts, with or without prior history by difficulty."""
    settings = context.difficulty
    with_history = context.active_accounts()
    everyone = context.accounts["account_id"].to_numpy()

    pool = with_history if with_history.size >= count else everyone
    use_history = context.rng.random(count) < settings.mule_history_fraction
    chosen = np.where(
        use_history,
        context.rng.choice(pool, size=count),
        context.rng.choice(everyone, size=count),
    )
    return chosen


def _victim_amount(context: InjectionContext, victim: str) -> float:
    """How much the victim is talked into sending."""
    settings = context.difficulty
    if context.rng.random() < settings.amount_from_history:
        # Hard: an amount this victim could plausibly have sent anyway.
        base = context.typical_amount(victim, fallback=900.0)
        return float(np.clip(base * context.rng.uniform(0.9, 2.4), 60.0, 40_000.0))
    # Easy: a conspicuous round sum.
    return float(context.rng.choice([1_500, 2_000, 3_000, 5_000, 8_000, 12_000]))


def inject(context: InjectionContext) -> InjectionResult:
    """Plant the configured number of mule chains."""
    rng = context.rng
    settings = context.difficulty
    fraud = context.fraud
    transactions: list[PlantedTransaction] = []
    cases: list[Case] = []

    if fraud.mule_chain_cases <= 0 or context.normal.height == 0:
        return InjectionResult()

    individuals = context.accounts.filter(context.accounts["holder_type"] == "PF")[
        "account_id"
    ].to_numpy()
    if individuals.size == 0:
        return InjectionResult()

    timestamps = context.normal["timestamp"].to_numpy()
    first, last = timestamps.min(), timestamps.max()
    span_seconds = max(int((last - first) / np.timedelta64(1, "s")), 1)

    for index in range(fraud.mule_chain_cases):
        case_id = f"case_{CODE}_{index + 1:05d}"
        depth = int(rng.integers(fraud.chain_depth_min, fraud.chain_depth_max + 1))
        victim = str(rng.choice(individuals))
        mules = _pick_mules(context, depth)
        roles: dict[str, str] = {victim: "victim"}

        amount = _victim_amount(context, victim)
        # Chains run during the day; the night limit would cap them.
        start_offset = int(rng.integers(0, span_seconds))
        moment = first + np.timedelta64(start_offset, "s")
        hour = moment.astype("datetime64[h]").astype(int) % 24
        if hour >= 20 or hour < 6:
            moment += np.timedelta64(int((10 - hour) % 24) * 3600, "s")

        chain_start = moment
        total = 0.0
        sender = victim
        for layer, mule in enumerate(mules, start=1):
            mule_id = str(mule)
            if mule_id == sender:
                continue
            role = "cash_out" if layer == depth else f"mule_layer_{layer}"
            roles[mule_id] = role

            transactions.append(
                PlantedTransaction(
                    src_account_id=sender,
                    dst_account_id=mule_id,
                    amount=round(amount, 2),
                    timestamp=moment,
                    channel="pix",
                    device_id=f"dev_{sender.removeprefix('acc_').lstrip('0') or '0'}",
                    case_id=case_id,
                    typology=CODE,
                    role="victim_payment" if layer == 1 else f"layer_{layer}",
                )
            )
            total += amount

            retained = rng.uniform(settings.retained_fraction_min, settings.retained_fraction_max)
            amount = max(amount * retained, 1.0)
            gap = rng.uniform(settings.hop_minutes_min, settings.hop_minutes_max)
            moment = moment + np.timedelta64(int(gap * 60), "s")
            sender = mule_id

        if not transactions:
            continue
        cases.append(
            Case(
                case_id=case_id,
                typology=CODE,
                difficulty=context.difficulty_name,
                start_ts=chain_start,
                end_ts=moment,
                depth=depth,
                total_amount=round(total, 2),
                accounts=roles,
                source_reference=SOURCE,
            )
        )
    return InjectionResult(transactions=transactions, cases=cases)
