"""Presentation-only race clock; never alters simulation state or finish order.

Course fields are read from the local master (1/10000 second units). The
conditional redraw follows the reverse-engineering report by @umamusu_reveng,
including the correction to a symmetric +/- range. Native RNG identity remains
unverified. Only the winner is assigned a corrected board time: how the native
client derives other runners' absolute board times has not been recovered.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math


@dataclass(frozen=True)
class RaceClock:
    scaled_finish_times: list[float]
    display_finish_times: list[float|None]
    metadata: dict


def build_race_clock(finish_times:list[float],course:dict,seed:int,coefficient:float) -> RaceClock:
    if not finish_times or any(not math.isfinite(t) or t<=0 for t in finish_times):
        raise ValueError('Finish times must be positive and finite')
    if not math.isfinite(coefficient) or coefficient<=0:
        raise ValueError('Invalid finish-time coefficient')
    winner=min(range(len(finish_times)),key=lambda i:(finish_times[i],i))
    scaled=[t*coefficient for t in finish_times]
    bounds={}
    for kind in ('min','max'):
        raw=course.get('finish_time_'+kind)
        value=float(raw)/10000 if raw is not None and raw>0 else None
        spread=float(course.get('finish_time_'+kind+'_random_range') or 0)/10000
        if (value is not None and not math.isfinite(value)) or not math.isfinite(spread) or spread<0:
            raise ValueError('Invalid course finish-time bounds')
        bounds[kind]={'seconds':value,'random_range_seconds':spread}
    lower,upper=bounds['min']['seconds'],bounds['max']['seconds']
    if lower is not None and upper is not None and lower>upper:
        raise ValueError('Course finish-time minimum exceeds maximum')
    value=scaled[winner]
    correction='lower' if lower is not None and value<lower else 'upper' if upper is not None and value>upper else 'none'
    draw=None
    if correction!='none':
        bound=bounds['min' if correction=='lower' else 'max']
        # Independent presentation stream: changing scoreboard rules cannot
        # consume a simulation RNG draw or affect an activation / ranking.
        digest=hashlib.sha256(f'uma-lab:board-clock:v1:{course.get("id",0)}:{seed}:{correction}'.encode()).digest()
        draw=(int.from_bytes(digest[:8],'big')>>11)/2**53
        value=bound['seconds']+(2*draw-1)*bound['random_range_seconds']
    display=[None for _ in finish_times]
    display[winner]=value
    return RaceClock(scaled,display,{
        'version':'course-bounds-1','coefficient':coefficient,'winner_runner':winner,
        'winner_scaled_time':scaled[winner],'winner_display_time':value,
        'correction':correction,'bounds':bounds,'presentation_draw':draw,
        'rng':'independent SHA256 presentation stream; native RNG not reproduced',
        'scope':'winner only; no invented correction to other runners or physical time gaps',
        'evidence':'local course bounds + published reverse-engineering rule; native method body unverified',
    })
